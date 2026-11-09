"""Exercise the actual packaged command using synthetic hook events."""

import json
import os
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "integrations/codex"


class SkillHookTests(unittest.TestCase):
    def invoke(self, payload, root=ROOT):
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run(
                ["/bin/sh", "-c", 'python3 "${PLUGIN_ROOT}/hooks/load_skills.py"'],
                input=payload,
                text=True,
                capture_output=True,
                cwd=cwd,
                env={"PATH": os.defpath, "PLUGIN_ROOT": str(root)},
                check=True,
                timeout=3,
            )
        return json.loads(result.stdout), result.stderr

    def test_all_events_have_matching_context(self):
        for event in ("SessionStart", "SubagentStart", "UserPromptSubmit"):
            with self.subTest(event=event):
                out, err = self.invoke(json.dumps({"hook_event_name": event}))
                output = out["hookSpecificOutput"]
                self.assertEqual(event, output["hookEventName"])
                self.assertIn("not authorization", output["additionalContext"])
                self.assertIn("not publish independently", output["additionalContext"])
                self.assertEqual("", err)
                self.assertNotIn("decision", out)

    def test_start_loads_actual_skill_bodies_and_absolute_locations(self):
        for event in ("SessionStart", "SubagentStart"):
            out, _ = self.invoke(json.dumps({"hook_event_name": event, "source": "compact"}))
            text = out["hookSpecificOutput"]["additionalContext"]
            for name in ("brain-recall", "brain-debrief"):
                path = ROOT / "skills" / name / "SKILL.md"
                self.assertIn(path.read_text(), text)
                self.assertIn(str(path), text)
            self.assertLess(len(text), 12000)

    def test_prompt_is_small_and_never_echoes_untrusted_input(self):
        out, _ = self.invoke(
            json.dumps(
                {"hook_event_name": "UserPromptSubmit", "prompt": "MALICIOUS_PRIVATE_SENTINEL"}
            )
        )
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("MALICIOUS_PRIVATE_SENTINEL", text)
        self.assertLess(len(text), 1400)
        self.assertNotIn("# Brain debrief", text)

    def test_bad_unknown_or_oversized_input_is_nonblocking(self):
        for raw in ("{", "[]", "null", '{"hook_event_name":"Stop"}', "x" * (1024**2 + 1)):
            with self.subTest(size=len(raw)):
                out, _ = self.invoke(raw)
                self.assertEqual({}, out)

    def test_missing_skill_does_not_inject_partial_instructions(self):
        with tempfile.TemporaryDirectory(prefix="plugin with spaces ") as directory:
            root = Path(directory)
            (root / "hooks").mkdir()
            (root / "hooks/load_skills.py").write_bytes(
                (ROOT / "hooks/load_skills.py").read_bytes()
            )
            out, err = self.invoke('{"hook_event_name":"SessionStart"}', root)
            self.assertEqual({}, out)
            self.assertIn("FileNotFoundError", err)

    def test_plan_mode_loads_instructions_without_running_runtime(self):
        out, _ = self.invoke(
            json.dumps(
                {
                    "hook_event_name": "SessionStart",
                    "permission_mode": "plan",
                    "transcript_path": "/nonexistent/private.jsonl",
                }
            )
        )
        self.assertIn("permission mode", out["hookSpecificOutput"]["additionalContext"])

    def test_tail_bridge_suppresses_continuation_and_ui_output_from_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "hooks").mkdir()
            (root / "scripts").mkdir()
            (root / "hooks/automatic.py").write_bytes((ROOT / "hooks/automatic.py").read_bytes())
            (root / "scripts/run.py").write_text(
                'import json\nprint(json.dumps({"decision":"block","reason":"follow up",'
                '"systemMessage":"replaces the task answer"}))\n'
            )
            for event in ("Stop", "SessionEnd"):
                result = subprocess.run(
                    [sys.executable, str(root / "hooks/automatic.py")],
                    input=json.dumps({"hook_event_name": event}),
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=3,
                )
                self.assertEqual({}, json.loads(result.stdout))

    def test_tail_bridge_failure_is_silent_in_ui(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "hooks").mkdir()
            (root / "hooks/automatic.py").write_bytes((ROOT / "hooks/automatic.py").read_bytes())
            result = subprocess.run(
                [sys.executable, str(root / "hooks/automatic.py")],
                input='{"hook_event_name":"Stop"}',
                capture_output=True,
                text=True,
                check=True,
                timeout=3,
            )
            self.assertEqual({}, json.loads(result.stdout))
            self.assertIn("deferred", result.stderr)


if __name__ == "__main__":
    unittest.main()
