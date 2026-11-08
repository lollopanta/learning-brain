"""Exercise installed automation commands with synthetic sessions in a disposable vault."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    plugin = args.plugin_root.resolve()
    with tempfile.TemporaryDirectory(prefix="brain automation synthetic ") as directory:
        root = Path(directory)
        vault = root / "vault"
        sources = root / "sources"
        settings = root / "config/learning-brain"
        for path in (vault, sources, settings):
            path.mkdir(parents=True)
        state = root / "state"
        config = settings / "config.toml"
        config.write_text(
            f"vault = {json.dumps(str(vault))}\nstate_dir = {json.dumps(str(state))}\n"
            f'source_roots = [{json.dumps(str(sources))}]\nautomation = "review"\n'
        )
        (settings / "runtime.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "executable": str(args.runtime.resolve()),
                    "config": str(config),
                }
            )
        )
        env = {
            **os.environ,
            "XDG_CONFIG_HOME": str(settings.parent),
            "PATH": os.defpath,
            "PLUGIN_ROOT": str(plugin),
            "LEARNING_BRAIN_CONFIG": str(config),
        }
        transcript = sources / "synthetic.jsonl"
        transcript.write_text(
            json.dumps({"type": "session_meta", "payload": {"id": "synthetic"}}) + "\n"
        )

        def append(role, text):
            with transcript.open("a") as stream:
                stream.write(
                    json.dumps(
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": role,
                                "content": [
                                    {
                                        "type": "input_text" if role == "user" else "output_text",
                                        "text": text,
                                    }
                                ],
                            },
                        }
                    )
                    + "\n"
                )

        def cli(*argv):
            run = subprocess.run(
                ["python3", str(plugin / "scripts/run.py"), *argv],
                capture_output=True,
                text=True,
                env=env,
                check=True,
                timeout=12,
            )
            return json.loads(run.stdout)

        def hook(event, **extra):
            payload = {
                "hook_event_name": event,
                "permission_mode": "default",
                "session_id": "synthetic",
                "turn_id": "turn-1",
                "transcript_path": str(transcript),
                **extra,
            }
            run = subprocess.run(
                ["python3", str(plugin / "hooks/automatic.py")],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                env=env,
                check=True,
                timeout=12,
            )
            return json.loads(run.stdout)

        checks = []
        append("user", "HISTORICAL_SENTINEL")
        assert (
            "automation=review" in hook("SessionStart")["hookSpecificOutput"]["additionalContext"]
        )
        assert cli("status")["jobs"] == []
        checks.append("baseline_excludes_history")
        append("user", "Use SQLite for the local prototype.")
        append("assistant", "SQLite is selected for the local prototype.")
        out = hook("Stop")
        assert out["decision"] == "block"
        jobs = cli("status")["jobs"]
        assert len(jobs) == 1 and jobs[0]["state"] == "queued"
        acquired = cli("inspect", jobs[0]["id"])
        assert "HISTORICAL_SENTINEL" not in json.dumps(acquired)
        checks.append("stop_acquires_delta_and_requests_debrief")
        assert hook("Stop") == {}
        assert hook("Stop", stop_hook_active=True) == {}
        checks.append("continuation_cannot_loop")
        assert "queued" in hook("UserPromptSubmit")["hookSpecificOutput"]["additionalContext"]
        checks.append("pending_jobs_surface_on_next_prompt")
        append("user", "A new user constraint.")
        assert hook("Stop", turn_id="turn-2", permission_mode="plan") == {}
        assert len(cli("status")["jobs"]) == 1
        checks.append("plan_mode_does_not_acquire")
        assert hook("SessionEnd") == {}
        assert len(cli("status")["jobs"]) == 2
        checks.append("session_end_captures_without_model")
        cli("automation-pause", "synthetic")
        append("user", "EXCLUDED_SENTINEL")
        assert hook("Stop", turn_id="turn-3") == {}
        assert len(cli("status")["jobs"]) == 2
        checks.append("session_pause_preserves_exclusion")
        assert list(vault.iterdir()) == []
        checks.append("personal_and_synthetic_vaults_untouched")
        print(
            json.dumps(
                {
                    "installed_automation": "pass",
                    "checks": checks,
                    "synthetic": True,
                    "model_started": False,
                    "automatic_semantic_selection": "requires live client validation",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
