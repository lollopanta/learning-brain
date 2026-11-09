import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from learning_brain.automation import MARKER, handle, pause
from learning_brain.config import Config
from learning_brain.errors import BrainError, Conflict
from learning_brain.proposals import prepare, review
from learning_brain.sources import capture
from learning_brain.store import Store


def message(role, text):
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": "input_text" if role == "user" else "output_text", "text": text}],
        },
    }


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.vault = root / "vault"
        self.sources = root / "sources"
        self.vault.mkdir()
        self.sources.mkdir()
        self.config = Config(self.vault, root / "state", (self.sources,), automation="review")
        self.path = self.sources / "session.jsonl"
        self.path.write_text(
            json.dumps({"type": "session_meta", "payload": {"id": "fixture"}}) + "\n"
        )
        self.append(message("user", "HISTORICAL_PRIVATE_SENTINEL"))

    def append(self, event):
        with self.path.open("a") as stream:
            stream.write(json.dumps(event) + "\n")

    def hook(self, kind, **extra):
        return {
            "hook_event_name": kind,
            "permission_mode": "default",
            "session_id": "fixture",
            "transcript_path": str(self.path),
            "turn_id": "turn-1",
            **extra,
        }

    def jobs(self):
        store = Store(self.config)
        try:
            return [store.job(row["id"]) for row in store.jobs()]
        finally:
            store.close()

    def arm(self):
        return handle(self.config, self.hook("UserPromptSubmit"))

    def test_default_off_and_plan_and_subagents_do_not_create_state(self):
        for config, event in (
            (replace(self.config, automation="off"), self.hook("Stop")),
            (self.config, self.hook("Stop", permission_mode="plan")),
            (self.config, self.hook("Stop", agent_id="child")),
            (self.config, self.hook("Stop", stop_hook_active=True)),
        ):
            self.assertEqual({}, handle(config, event))
        self.assertFalse(self.config.state.exists())

    def test_baseline_excludes_history_and_stop_captures_only_delta(self):
        self.arm()
        self.assertEqual([], self.jobs())
        self.append(message("user", "Use SQLite for the local prototype."))
        out = handle(self.config, self.hook("Stop"))
        self.assertEqual({}, out)
        jobs = self.jobs()
        self.assertEqual(1, len(jobs))
        self.assertNotIn("HISTORICAL_PRIVATE_SENTINEL", json.dumps(jobs))
        self.assertIn("Use SQLite", jobs[0]["payload"]["messages"][0]["text"])
        self.assertEqual([], list(self.vault.iterdir()))

    def test_automatic_acquisition_can_stage_real_review_bundle_without_publish(self):
        self.arm()
        self.append(message("user", "Use SQLite for the local prototype."))
        handle(self.config, self.hook("Stop"))
        store = Store(self.config)
        try:
            job = store.job(store.jobs()[0]["id"])
            msg = job["payload"]["messages"][0]
            prepare(
                store,
                job["id"],
                {
                    "schema_version": 1,
                    "updates": [
                        {
                            "path": "concepts/storage.md",
                            "expected_revision": None,
                            "kind": "decision",
                            "title": "Storage",
                            "summary": "SQLite for the local prototype.",
                            "tags": ["storage"],
                            "claims": [
                                {
                                    "text": "SQLite is selected for the local prototype.",
                                    "epistemic": "user_stated",
                                    "evidence": [{"message_id": msg["id"], "quote": msg["text"]}],
                                }
                            ],
                        }
                    ],
                },
            )
            self.assertTrue(review(store, job["id"]))
            self.assertEqual("staged", store.job(job["id"])["state"])
        finally:
            store.close()
        self.assertEqual([], list(self.vault.iterdir()))

    def test_repeated_stop_and_active_continuation_cannot_loop_or_capture_maintenance(self):
        self.arm()
        self.append(message("user", "A new decision."))
        self.assertEqual({}, handle(self.config, self.hook("Stop")))
        size = len(self.jobs())
        self.append(message("assistant", "Maintenance reply."))
        self.assertEqual({}, handle(self.config, self.hook("Stop")))
        self.assertEqual({}, handle(self.config, self.hook("Stop", stop_hook_active=True)))
        self.assertEqual(size, len(self.jobs()))

    def test_next_turn_captures_without_continuing(self):
        self.arm()
        self.append(message("user", "First decision."))
        handle(self.config, self.hook("Stop"))
        self.append(message("user", "Second decision."))
        self.assertEqual({}, handle(self.config, self.hook("Stop", turn_id="turn-2")))
        self.assertEqual(2, len(self.jobs()))

    def test_session_end_acquires_without_continuing(self):
        self.arm()
        self.append(message("user", "Decision at session end."))
        self.assertEqual({}, handle(self.config, self.hook("SessionEnd")))
        self.assertEqual("queued", self.jobs()[0]["state"])

    def test_session_end_without_permission_mode_does_not_infer_capture_permission(self):
        event = self.hook("SessionEnd")
        event.pop("permission_mode")
        self.assertEqual({}, handle(self.config, event))
        self.assertFalse(self.config.state.exists())

    def test_stop_without_start_anchors_instead_of_importing_history(self):
        self.assertEqual({}, handle(self.config, self.hook("Stop")))
        self.assertEqual([], self.jobs())

    def test_missing_or_mismatched_identity_cannot_acquire(self):
        for event in (
            self.hook("Stop", session_id="wrong"),
            self.hook("Stop", transcript_path="/tmp/not-allowed.jsonl"),
            self.hook("Stop", transcript_path="relative.jsonl"),
        ):
            with self.assertRaises((BrainError, OSError)):
                handle(self.config, event)
        self.assertFalse(self.config.state.exists())

    def test_pause_prevents_capture_and_preserves_existing_jobs(self):
        self.arm()
        self.append(message("user", "Before pause."))
        handle(self.config, self.hook("Stop"))
        pause(self.config, "fixture")
        self.append(message("user", "EXCLUDED_SENTINEL"))
        self.assertEqual({}, handle(self.config, self.hook("Stop", turn_id="turn-2")))
        self.assertNotIn("EXCLUDED_SENTINEL", json.dumps(self.jobs()))
        self.assertEqual(1, len(self.jobs()))

    def test_partial_tail_is_not_consumed_in_baseline(self):
        full = json.dumps(message("user", "Complete after arm.")) + "\n"
        with self.path.open("a") as stream:
            stream.write(full[:20])
        self.arm()
        with self.path.open("a") as stream:
            stream.write(full[20:])
        self.assertEqual({}, handle(self.config, self.hook("Stop")))
        self.assertEqual("Complete after arm.", self.jobs()[0]["payload"]["messages"][0]["text"])

    def test_rewritten_source_is_rejected_without_advancing(self):
        self.arm()
        self.path.write_text(self.path.read_text().replace("HISTORICAL", "MODIFIEDXX"))
        with self.assertRaises(Conflict):
            handle(self.config, self.hook("Stop"))
        self.assertEqual([], self.jobs())

    def test_synthetic_continuation_is_not_eligible_user_evidence(self):
        self.arm()
        self.append(message("user", MARKER + " Synthetic maintenance prompt."))
        self.assertEqual({}, handle(self.config, self.hook("Stop")))
        self.assertEqual([], self.jobs()[0]["payload"]["messages"])

    def test_codex_wrapped_hook_prompt_is_excluded_but_real_user_message_survives(self):
        self.arm()
        self.append(
            message(
                "user",
                '<hook_prompt hook_run_id="synthetic:stop">'
                + MARKER
                + " Automatic maintenance.</hook_prompt>",
            )
        )
        self.append(message("user", "Keep the actual project decision."))
        self.assertEqual({}, handle(self.config, self.hook("Stop")))
        messages = self.jobs()[0]["payload"]["messages"]
        self.assertEqual(1, len(messages))
        self.assertEqual("Keep the actual project decision.", messages[0]["text"])

    def test_manual_checkpoint_is_preserved_and_empty_stop_does_not_continue(self):
        store = Store(self.config)
        try:
            capture(store, self.path)
        finally:
            store.close()
        before = self.jobs()
        self.arm()
        self.assertEqual(before, self.jobs())
        # A prior queue is surfaced at prompt time; no extra continuation without new messages.
        self.assertEqual({}, handle(self.config, self.hook("Stop")))

    def test_invalid_automation_mode_rejected(self):
        with self.assertRaises(BrainError):
            replace(self.config, automation="publish")

    def test_autonomous_routing_is_opt_in_and_hook_itself_never_publishes(self):
        self.config = replace(self.config, automation="autonomous")
        out = self.arm()
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("automation=autonomous", text)
        self.assertIn("agent:self-review", text)
        self.assertIn(str(self.path), text)
        self.append(message("user", "A genuine project decision."))
        self.assertEqual({}, handle(self.config, self.hook("Stop")))
        self.assertEqual("queued", self.jobs()[0]["state"])
        self.assertEqual([], list(self.vault.iterdir()))

    def test_review_mode_does_not_authorize_autonomous_publication(self):
        text = self.arm()["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Never auto-apply", text)
        self.assertNotIn("reviewer agent:self-review", text)

    def test_next_prompt_recovers_prior_final_without_a_stop_followup(self):
        self.config = replace(self.config, automation="autonomous")
        self.arm()
        self.append(message("assistant", "A prior task's final result."))
        out = handle(self.config, self.hook("UserPromptSubmit", turn_id="turn-2"))
        jobs = self.jobs()
        self.assertEqual(1, len(jobs))
        self.assertIn(jobs[0]["id"], out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual("A prior task's final result.", jobs[0]["payload"]["messages"][0]["text"])
        self.assertNotIn("decision", out)
