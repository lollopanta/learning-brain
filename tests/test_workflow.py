import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from learning_brain.adapters import WikiAdapter
from learning_brain.config import Config, load
from learning_brain.errors import BrainError, Conflict
from learning_brain.fs import inside, revision, writer_lock
from learning_brain.hooks import record
from learning_brain.notes import parse_note
from learning_brain.proposals import prepare, review
from learning_brain.publishing import apply
from learning_brain.sources import capture
from learning_brain.store import Store


def event(role, text, channel=None):
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "channel": channel,
            "content": [{"type": "input_text" if role == "user" else "output_text", "text": text}],
        },
    }


def encode(events):
    return b"".join((json.dumps(item) + "\n").encode() for item in events)


class FakeAdapter:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def preflight(self):
        return {"version": "fixture"}

    def finalize(self, bundle):
        self.calls += 1
        if self.fail:
            raise BrainError("Injected adapter failure")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.vault = root / "vault"
        self.sources = root / "sessions"
        self.vault.mkdir()
        self.sources.mkdir()
        self.config = Config(self.vault, root / "state", (self.sources,))
        self.store = Store(self.config)
        self.addCleanup(self.store.close)
        self.path = self.sources / "rollout.jsonl"
        self.events = [
            {"type": "session_meta", "payload": {"id": "test-session"}},
            event("user", "We chose SQLite because one writer is enough."),
            event("assistant", "The fixture test passes.", "final"),
        ]
        self.path.write_bytes(encode(self.events))
        self.adapter = FakeAdapter()

    def acquire(self):
        return capture(self.store, self.path)["job_id"]

    def proposal(self, job_id, target="concepts/storage.md", expected=None):
        message = self.store.job(job_id)["payload"]["messages"][0]
        return {
            "schema_version": 1,
            "updates": [
                {
                    "path": target,
                    "expected_revision": expected,
                    "kind": "decision",
                    "title": "Storage decision",
                    "summary": "SQLite supports the single writer workflow.",
                    "tags": ["storage"],
                    "claims": [
                        {
                            "text": "SQLite was selected for the single writer workflow.",
                            "epistemic": "user_stated",
                            "evidence": [{"message_id": message["id"], "quote": message["text"]}],
                        }
                    ],
                }
            ],
        }

    def stage(self, job_id=None, **kwargs):
        job_id = job_id or self.acquire()
        staged = prepare(self.store, job_id, self.proposal(job_id, **kwargs))
        return job_id, staged["review_token"]

    def publish(self, job_id, token, **kwargs):
        return apply(self.store, job_id, token, "fixture-reviewer", self.adapter, **kwargs)

    def test_replayed_acquisition_has_no_duplicate_job(self):
        self.acquire()
        self.assertIsNone(capture(self.store, self.path)["job_id"])
        self.assertEqual(len(self.store.jobs()), 1)

    def test_active_session_append_only_acquires_delta(self):
        first = self.acquire()
        with self.path.open("ab") as stream:
            stream.write(encode([event("user", "Next, evaluate recovery.")]))
        second = self.acquire()
        self.assertNotEqual(first, second)
        payload = self.store.job(second)["payload"]
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["start"], self.store.job(first)["end"])

    def test_partial_last_line_is_not_checkpointed(self):
        original = self.path.read_bytes()
        tail = encode([event("user", "A complete future event.")])
        self.path.write_bytes(original + tail[:-5])
        first = self.acquire()
        self.assertEqual(self.store.job(first)["end"], len(original))
        with self.path.open("ab") as stream:
            stream.write(tail[-5:])
        self.assertEqual(len(self.store.job(self.acquire())["payload"]["messages"]), 1)

    def test_rewritten_source_does_not_advance_checkpoint(self):
        self.acquire()
        before = dict(self.store.db.execute("SELECT * FROM sources").fetchone())
        self.path.write_bytes(self.path.read_bytes().replace(b"SQLite", b"MySQL!"))
        with self.assertRaises(Conflict):
            self.acquire()
        self.assertEqual(dict(self.store.db.execute("SELECT * FROM sources").fetchone()), before)

    def test_truncated_source_is_a_conflict(self):
        self.acquire()
        self.path.write_bytes(encode(self.events[:1]))
        with self.assertRaises(Conflict):
            self.acquire()

    def test_malformed_complete_event_rolls_back_entire_capture(self):
        with self.path.open("ab") as stream:
            stream.write(b"{invalid}\n")
        with self.assertRaises(BrainError):
            self.acquire()
        self.assertEqual(self.store.jobs(), [])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM sources").fetchone()[0], 0)

    def test_reasoning_instructions_and_tool_outputs_are_excluded(self):
        extra = [
            event("assistant", "INTERNAL_REASONING", "analysis"),
            event("system", "SYSTEM_INSTRUCTION"),
            event("developer", "DEVELOPER_INSTRUCTION"),
            {
                "type": "response_item",
                "payload": {"type": "function_call_output", "output": "TOOL_OUTPUT"},
            },
        ]
        self.path.write_bytes(encode([*self.events, *extra]))
        text = json.dumps(self.store.job(self.acquire())["payload"])
        for forbidden in (
            "INTERNAL_REASONING",
            "SYSTEM_INSTRUCTION",
            "DEVELOPER_INSTRUCTION",
            "TOOL_OUTPUT",
        ):
            self.assertNotIn(forbidden, text)

    def test_known_secret_patterns_are_redacted_before_storage(self):
        self.path.write_bytes(
            encode([*self.events, event("user", "api_key=abc123 password=hunter2")])
        )
        text = json.dumps(self.store.job(self.acquire())["payload"])
        self.assertNotIn("abc123", text)
        self.assertNotIn("hunter2", text)

    def test_source_outside_allowlist_is_refused(self):
        other = Path(self.tmp.name) / "other.jsonl"
        other.write_bytes(self.path.read_bytes())
        with self.assertRaises(BrainError):
            capture(self.store, other)

    def test_unknown_message_format_fails_without_checkpoint(self):
        self.path.write_bytes(
            encode(
                [
                    self.events[0],
                    {
                        "type": "response_item",
                        "payload": {"type": "message", "role": "user", "content": "changed format"},
                    },
                ]
            )
        )
        with self.assertRaises(BrainError):
            self.acquire()
        self.assertEqual(self.store.jobs(), [])

    def test_unknown_message_block_cannot_be_silently_skipped(self):
        self.path.write_bytes(
            encode(
                [
                    self.events[0],
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": "new_text_format",
                                    "text": "A potentially important decision",
                                }
                            ],
                        },
                    },
                ]
            )
        )
        with self.assertRaises(BrainError):
            self.acquire()
        self.assertEqual(self.store.jobs(), [])

    def test_evidence_must_match_exact_acquired_text(self):
        job = self.acquire()
        proposal = self.proposal(job)
        proposal["updates"][0]["claims"][0]["evidence"][0]["quote"] = "Invented proof"
        with self.assertRaises(BrainError):
            prepare(self.store, job, proposal)
        self.assertEqual(self.store.job(job)["state"], "queued")

    def test_assistant_evidence_cannot_be_labelled_user_stated(self):
        job = self.acquire()
        proposal = self.proposal(job)
        message = self.store.job(job)["payload"]["messages"][1]
        proposal["updates"][0]["claims"][0]["evidence"] = [
            {"message_id": message["id"], "quote": message["text"]}
        ]
        with self.assertRaises(BrainError):
            prepare(self.store, job, proposal)

    def test_review_and_prepare_never_write_to_vault(self):
        job, _ = self.stage()
        self.assertIn("diff", review(self.store, job)["diffs"][0])
        self.assertEqual(list(self.vault.iterdir()), [])

    def test_changed_live_note_is_not_overwritten(self):
        job, token = self.stage()
        target = self.vault / "concepts/storage.md"
        target.parent.mkdir()
        target.write_text("A concurrent edit")
        with self.assertRaises(Conflict):
            self.publish(job, token)
        self.assertEqual(target.read_text(), "A concurrent edit")
        self.assertFalse((self.vault / "_raw").exists())

    def test_stale_review_token_cannot_publish_new_proposal(self):
        job, old_token = self.stage()
        proposal = self.proposal(job)
        proposal["updates"][0]["summary"] = "A changed summary."
        prepare(self.store, job, proposal)
        with self.assertRaises(BrainError):
            self.publish(job, old_token)
        self.assertFalse((self.vault / "concepts").exists())

    def test_replay_publication_does_not_repeat_finalization(self):
        job, token = self.stage()
        self.publish(job, token)
        result = self.publish(job, token)
        self.assertTrue(result["replay"])
        self.assertEqual(self.adapter.calls, 1)

    def test_crash_after_each_file_is_recoverable(self):
        for failure_after in (1, 2):
            with self.subTest(failure_after=failure_after):
                job, token = self.stage(target=f"concepts/recovery-{failure_after}.md")
                count = 0

                def crash(_, failure_after=failure_after):
                    nonlocal count
                    count += 1
                    if count == failure_after:
                        raise RuntimeError("simulated process death")

                with self.assertRaises(RuntimeError):
                    self.publish(job, token, after_write=crash)
                self.assertEqual(self.store.job(job)["state"], "publishing")
                self.store.close()
                self.store = Store(self.config)
                self.addCleanup(self.store.close)
                self.publish(job, token)
                self.assertEqual(self.store.job(job)["state"], "published")
                # A later interval is a separate acquisition, as in a long running session.
                with self.path.open("ab") as stream:
                    stream.write(
                        encode([event("user", "We chose SQLite because one writer is enough.")])
                    )

    def test_adapter_failure_preserves_recoverable_intent(self):
        job, token = self.stage()
        self.adapter.fail = True
        with self.assertRaises(BrainError):
            self.publish(job, token)
        self.assertEqual(self.store.job(job)["state"], "publishing")
        self.adapter.fail = False
        self.publish(job, token)
        self.assertEqual(self.store.job(job)["state"], "published")

    def test_partial_batch_recovers_without_rewriting_completed_pages(self):
        job = self.acquire()
        proposal = self.proposal(job)
        second = json.loads(json.dumps(proposal["updates"][0]))
        second["path"] = "concepts/second.md"
        proposal["updates"].append(second)
        token = prepare(self.store, job, proposal)["review_token"]

        def crash(path):
            if path == "concepts/storage.md":
                raise RuntimeError("crash between pages")

        with self.assertRaises(RuntimeError):
            self.publish(job, token, after_write=crash)
        first_revision = revision(self.vault / "concepts/storage.md")
        self.publish(job, token)
        self.assertEqual(revision(self.vault / "concepts/storage.md"), first_revision)
        self.assertTrue((self.vault / "concepts/second.md").exists())

    def test_missing_source_prevents_publication(self):
        job, token = self.stage()
        self.path.unlink()
        with self.assertRaises(BrainError):
            self.publish(job, token)
        self.assertFalse((self.vault / "concepts").exists())

    def test_source_modified_after_review_prevents_publication(self):
        job, token = self.stage()
        self.path.write_bytes(self.path.read_bytes().replace(b"SQLite", b"MySQL!"))
        with self.assertRaises(Conflict):
            self.publish(job, token)

    def test_update_preserves_body_and_unknown_metadata(self):
        target = self.vault / "concepts/storage.md"
        target.parent.mkdir()
        target.write_text(
            "---\ntitle: Storage\ncategory: concepts\nlifecycle: verified\n"
            "custom: preserved\nsources: [repo:example]\n---\n\n"
            "# Existing\n\nImportant original reasoning.\n\n## Sources\n\n- old\n"
        )
        job, token = self.stage(expected=revision(target))
        self.publish(job, token)
        header, body = parse_note(target.read_text())
        self.assertIn("Important original reasoning.", body)
        self.assertEqual(header["custom"], "preserved")
        self.assertEqual(header["title"], "Storage decision")
        self.assertEqual(header["tags"], ["storage"])
        self.assertEqual(header["lifecycle"], "draft")
        self.assertIn("repo:example", header["sources"])

    def test_duplicate_yaml_keys_are_refused(self):
        with self.assertRaises(BrainError):
            parse_note("---\ntitle: A\ntitle: B\n---\nbody")

    def test_service_files_traversal_and_symlinks_are_refused(self):
        job = self.acquire()
        for target in ("../outside.md", "_meta/profile.md", "/absolute.md", "log.md"):
            with self.subTest(target=target), self.assertRaises(BrainError):
                prepare(self.store, job, self.proposal(job, target))
        (self.vault / "concepts").symlink_to(self.sources, target_is_directory=True)
        with self.assertRaises(BrainError):
            prepare(self.store, job, self.proposal(job))

    def test_skip_records_reason_and_is_terminal(self):
        job = self.acquire()
        self.store.skip(job, "Already covered by existing knowledge")
        self.store.skip(job, "repeat")
        self.assertEqual(self.store.job(job)["error"], "Already covered by existing knowledge")
        with self.assertRaises(BrainError):
            prepare(self.store, job, self.proposal(job))

    def test_state_directory_cannot_be_reused_for_another_vault(self):
        other = self.vault.parent / "another-vault"
        other.mkdir()
        with self.assertRaises(BrainError):
            Store(replace(self.config, vault=other))

    def test_second_publisher_cannot_enter_same_lock(self):
        path = inside(self.vault, ".learning-brain.lock")
        with writer_lock(path), self.assertRaises(BrainError), writer_lock(path):
            self.fail("second writer entered")

    def test_open_thread_requires_direct_user_evidence(self):
        job = self.acquire()
        proposal = self.proposal(job)
        assistant = self.store.job(job)["payload"]["messages"][1]
        proposal["open_threads"] = [
            {
                "text": "Evaluate recovery",
                "origin": "concepts/storage.md",
                "evidence": [{"message_id": assistant["id"], "quote": assistant["text"]}],
            }
        ]
        with self.assertRaises(BrainError):
            prepare(self.store, job, proposal)

    def test_hook_only_records_a_reference_and_never_touches_vault(self):
        payload = {
            "session_id": "test",
            "transcript_path": str(self.path),
            "turn_id": "one",
            "hook_event_name": "Stop",
        }
        record(self.config, payload)
        record(self.config, payload)
        self.assertEqual(len(list((self.config.state / "requests").glob("*.json"))), 1)
        self.assertEqual(list(self.vault.iterdir()), [])
        self.assertNotIn(
            "SQLite", next((self.config.state / "requests").glob("*.json")).read_text()
        )

    def test_hook_respects_plan_mode_and_recursion_guard(self):
        for extra in ({"permission_mode": "plan"}, {"stop_hook_active": True}):
            result = record(self.config, {"hook_event_name": "Stop", **extra})
            self.assertEqual(result["state"], "skipped")
        self.assertFalse((self.config.state / "requests").exists())

    def test_qmd_failure_reports_pending_without_changing_publication(self):
        job, token = self.stage()
        self.publish(job, token)
        config = replace(self.config, qmd_command=("qmd",))
        with patch("learning_brain.adapters.subprocess.run", side_effect=OSError("offline")):
            self.assertEqual(WikiAdapter(config).refresh_search()["state"], "pending")
        self.assertEqual(self.store.job(job)["state"], "published")

    def test_adapter_rejects_unsupported_release(self):
        adapter = WikiAdapter(self.config)
        with patch.object(adapter, "run", return_value="obsidian-wiki 0.0.0"):
            with self.assertRaises(BrainError):
                adapter.preflight()

    def test_config_rejects_unknown_keys_and_state_inside_vault(self):
        path = Path(self.tmp.name) / "config.toml"
        content = f'vault = "{self.vault}"\nsource_roots = ["{self.sources}"]\n'
        path.write_text(content + "typo = true\n")
        with self.assertRaises(BrainError):
            load(path)
        path.write_text(content + f'state_dir = "{self.vault / "state"}"\n')
        with self.assertRaises(BrainError):
            load(path)

    def test_missing_input_returns_structured_cli_error(self):
        # CLI errors remain machine-readable; arbitrary payloads aren't printed.
        config = Path(self.tmp.name) / "config.toml"
        config.write_text(
            f'vault = "{self.vault}"\nsource_roots = ["{self.sources}"]\n'
            f'state_dir = "{self.config.state}"\n'
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "learning_brain",
                "--config",
                str(config),
                "capture",
                str(self.sources / "absent"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("error", json.loads(result.stderr))
        self.assertNotIn("Traceback", result.stderr)

    def test_bounded_capture_eventually_acquires_all_complete_messages(self):
        self.store.close()
        self.store = Store(replace(self.config, max_capture_bytes=1024))
        self.addCleanup(self.store.close)
        events = [
            self.events[0],
            *[event("user", "message " + str(i) + " " + "x" * 150) for i in range(20)],
        ]
        self.path.write_bytes(encode(events))
        seen = []
        for _ in range(30):
            result = capture(self.store, self.path)
            if result["job_id"]:
                seen.extend(self.store.job(result["job_id"])["payload"]["messages"])
            if not result["more_available"]:
                break
        self.assertEqual(len(seen), 20)
        self.assertEqual(len({message["id"] for message in seen}), 20)

    def test_oversize_single_event_preserves_checkpoint(self):
        self.store.close()
        self.store = Store(replace(self.config, max_capture_bytes=1024))
        self.addCleanup(self.store.close)
        self.path.write_bytes(encode([self.events[0], event("user", "x" * 5000)]))
        first = capture(self.store, self.path)
        self.assertTrue(first["more_available"])
        offset = self.store.db.execute("SELECT offset FROM sources").fetchone()[0]
        with self.assertRaises(BrainError):
            capture(self.store, self.path)
        self.assertEqual(self.store.db.execute("SELECT offset FROM sources").fetchone()[0], offset)

    def test_partial_only_tail_keeps_hook_request_pending(self):
        from learning_brain.cli import execute, parser

        self.acquire()
        with self.path.open("ab") as stream:
            stream.write(b'{"type": "response_item"')
        record(
            self.config,
            {
                "session_id": "test",
                "transcript_path": str(self.path),
                "turn_id": "partial",
                "hook_event_name": "Stop",
            },
        )
        config = Path(self.tmp.name) / "config.toml"
        config.write_text(
            f'vault = "{self.vault}"\nsource_roots = ["{self.sources}"]\n'
            f'state_dir = "{self.config.state}"\n'
        )
        args = parser().parse_args(["--config", str(config), "drain"])
        result = execute(args)
        self.assertTrue(result["acquisitions"][0]["more_available"])
        self.assertEqual(len(list((self.config.state / "requests").glob("*.json"))), 1)

    def test_actual_process_exit_releases_lock_and_recovers_journal(self):
        job, token = self.stage()
        config = Path(self.tmp.name) / "config.toml"
        config.write_text(
            f'vault = "{self.vault}"\nsource_roots = ["{self.sources}"]\n'
            f'state_dir = "{self.config.state}"\n'
        )
        script = """
import os, sys
from pathlib import Path
from learning_brain.config import load
from learning_brain.store import Store
from learning_brain.publishing import apply
class FixtureAdapter:
    def preflight(self): pass
    def finalize(self, bundle): pass
store = Store(load(Path(sys.argv[1])))
apply(store, sys.argv[2], sys.argv[3], 'fixture-reviewer', FixtureAdapter(),
      after_write=lambda _: os._exit(23))
"""
        result = subprocess.run(
            [sys.executable, "-c", script, str(config), job, token], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(self.store.job(job)["state"], "publishing")
        self.publish(job, token)
        self.assertEqual(self.store.job(job)["state"], "published")

    def test_existing_snapshot_cannot_be_silently_replaced(self):
        job, token = self.stage()
        snapshot = self.store.job(job)["bundle"]["snapshot"]["path"]
        target = self.vault / snapshot
        target.parent.mkdir(parents=True)
        target.write_text("Another writer's snapshot")
        with self.assertRaises(Conflict):
            self.publish(job, token)
        self.assertEqual(target.read_text(), "Another writer's snapshot")

    def test_recovery_refuses_a_different_reviewer_identity(self):
        job, token = self.stage()
        self.adapter.fail = True
        with self.assertRaises(BrainError):
            self.publish(job, token)
        with self.assertRaises(BrainError):
            apply(self.store, job, token, "different-reviewer", self.adapter)

    def test_empty_sources_heading_does_not_create_duplicate_section(self):
        target = self.vault / "concepts/storage.md"
        target.parent.mkdir()
        target.write_text(
            "---\ntitle: Storage\ncategory: concepts\nlifecycle: draft\n---\n\n"
            "# Existing\n\n## Sources\n"
        )
        job, token = self.stage(expected=revision(target))
        self.publish(job, token)
        self.assertEqual(target.read_text().count("## Sources"), 1)

    def test_malformed_proposal_types_are_actionable_errors(self):
        job = self.acquire()
        for key, value in (("epistemic", []), ("evidence", "not a list")):
            proposal = self.proposal(job)
            proposal["updates"][0]["claims"][0][key] = value
            with self.subTest(key=key), self.assertRaises(BrainError):
                prepare(self.store, job, proposal)
        proposal = self.proposal(job)
        proposal["updates"][0]["claims"][0]["evidence"][0]["message_id"] = []
        with self.assertRaises(BrainError):
            prepare(self.store, job, proposal)

    def test_generated_related_links_must_resolve(self):
        job = self.acquire()
        proposal = self.proposal(job)
        proposal["updates"][0]["related"] = ["concepts/missing.md"]
        with self.assertRaises(BrainError):
            prepare(self.store, job, proposal)

    def test_new_content_does_not_clear_an_existing_dispute(self):
        target = self.vault / "concepts/storage.md"
        target.parent.mkdir()
        target.write_text(
            "---\ntitle: Storage\ncategory: concepts\nlifecycle: disputed\n"
            "lifecycle_changed: '2026-01-01'\n---\n\n"
            "# Existing\n\nAn unresolved contradiction.\n"
        )
        job, token = self.stage(expected=revision(target))
        self.publish(job, token)
        header, body = parse_note(target.read_text())
        self.assertEqual(header["lifecycle"], "disputed")
        self.assertEqual(header["lifecycle_changed"], "2026-01-01")
        self.assertIn("An unresolved contradiction.", body)

    def test_adapter_refuses_corrupt_manifest_before_cli_writes(self):
        (self.vault / ".manifest.json").write_text("{broken")
        with patch.object(WikiAdapter, "run", return_value="obsidian-wiki 2026.10.2"):
            with self.assertRaises(BrainError):
                WikiAdapter(self.config).preflight()
        self.assertEqual((self.vault / ".manifest.json").read_text(), "{broken")

    def test_adapter_refuses_symlinked_service_directory(self):
        (self.vault / "_meta").symlink_to(self.sources, target_is_directory=True)
        with patch.object(WikiAdapter, "run", return_value="obsidian-wiki 2026.10.2"):
            with self.assertRaises(BrainError):
                WikiAdapter(self.config).preflight()

    def test_correction_precedes_old_intro_and_preserves_history(self):
        target = self.vault / "concepts/storage.md"
        target.parent.mkdir()
        target.write_text(
            "---\ntitle: Storage\ncategory: concepts\nlifecycle: verified\n---\n\n"
            "# Storage\n\nA stale deployment assertion.\n\n" + "Historical detail.\n\n" * 100
        )
        job = self.acquire()
        proposal = self.proposal(job, expected=revision(target))
        proposal["updates"][0]["kind"] = "correction"
        token = prepare(self.store, job, proposal)["review_token"]
        self.publish(job, token)
        header, body = parse_note(target.read_text())
        self.assertEqual(header["lifecycle"], "disputed")
        self.assertLess(
            body.index("SQLite was selected"), body.index("A stale deployment assertion.")
        )
        self.assertIn("Previous content (historical)", body)
        self.assertEqual(body.count("Historical detail."), 100)


if __name__ == "__main__":
    unittest.main()
