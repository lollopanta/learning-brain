"""Executable integration check using synthetic messages and a disposable vault only."""

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from learning_brain.adapters import WikiAdapter
from learning_brain.config import Config
from learning_brain.errors import Conflict
from learning_brain.notes import parse_note
from learning_brain.proposals import prepare, review
from learning_brain.publishing import apply
from learning_brain.sources import capture
from learning_brain.store import Store


def main():
    wiki = shutil.which("obsidian-wiki")
    if not wiki:
        raise SystemExit("Install obsidian-wiki==2026.10.2 to run this optional integration check")
    with tempfile.TemporaryDirectory(prefix="learning-brain-demo-") as temp:
        root = Path(temp).resolve()
        vault = root / "vault"
        vault.mkdir()
        sessions = root / "sessions"
        sessions.mkdir()
        for name in ("index", "log", "hot"):
            (vault / f"{name}.md").write_text(f"# {name.title()}\n")
        (vault / ".manifest.json").write_text('{"sources": {}, "projects": {}}\n')
        subprocess.run(
            [wiki, "memory", "migrate", "--vault", str(vault), "--apply"],
            check=True,
            capture_output=True,
            text=True,
        )
        transcript = sessions / "synthetic.jsonl"
        message = "Use SQLite for one local writer. Next, validate restart recovery."
        events = [
            {"type": "session_meta", "payload": {"id": "synthetic-demo"}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": message}],
                },
            },
        ]
        transcript.write_text("".join(json.dumps(event) + "\n" for event in events))
        config = Config(vault, root / "state", (sessions,), (wiki,))
        store = Store(config)
        try:
            adapter = WikiAdapter(config)
            compatibility = adapter.preflight()
            job = capture(store, transcript)["job_id"]
            message_id = store.job(job)["payload"]["messages"][0]["id"]
            evidence = [{"message_id": message_id, "quote": message}]
            proposal = {
                "schema_version": 1,
                "updates": [
                    {
                        "path": "concepts/local-storage.md",
                        "expected_revision": None,
                        "kind": "decision",
                        "title": "Local storage",
                        "summary": "SQLite for one writer.",
                        "tags": ["storage"],
                        "claims": [
                            {
                                "text": "SQLite is selected for one local writer.",
                                "epistemic": "user_stated",
                                "evidence": evidence,
                            }
                        ],
                    }
                ],
                "open_threads": [
                    {
                        "text": "Validate restart recovery",
                        "origin": "concepts/local-storage.md",
                        "evidence": evidence,
                    }
                ],
            }
            prepare(store, job, proposal)
            reviewed = review(store, job)
            token = reviewed["review_token"]
            # Fixture approval is explicitly not a real human/semantic pilot.
            apply(store, job, token, "synthetic-fixture", adapter)
            assert apply(store, job, token, "synthetic-fixture", adapter)["replay"]
            assert capture(store, transcript)["job_id"] is None
            header, body = parse_note((vault / "concepts/local-storage.md").read_text())
            assert header["lifecycle"] == "draft"
            assert "user_stated" in body
            assert "concepts/local-storage" in (vault / "index.md").read_text()
            assert (vault / "log.md").read_text().count(f"operation_id={job}") == 1
            manifest = json.loads((vault / ".manifest.json").read_text())
            origin = store.job(job)["bundle"]["origin"]
            assert origin in manifest["sources"]
            snapshot = f"_raw/_archived/learning-brain/{job}.md"
            assert snapshot in manifest["sources"]
            todos = adapter.run(["memory", "todo", "list", "--vault", str(vault), "--json"])
            assert "Validate restart recovery" in todos
            # The real CLI can finish tracking again without duplicating an operation log.
            adapter.finalize(store.job(job)["bundle"])
            assert (vault / "log.md").read_text().count(f"operation_id={job}") == 1
            # Source growth produces a new acquisition; an intervening edit blocks publication.
            with transcript.open("a") as stream:
                stream.write(json.dumps(events[1]) + "\n")
            second = capture(store, transcript)["job_id"]
            second_proposal = json.loads(json.dumps(proposal))
            second_proposal["updates"][0]["expected_revision"] = hashlib.sha256(
                (vault / "concepts/local-storage.md").read_bytes()
            ).hexdigest()
            ref = store.job(second)["payload"]["messages"][0]["id"]
            for item in (
                second_proposal["updates"][0]["claims"][0],
                second_proposal["open_threads"][0],
            ):
                item["evidence"][0]["message_id"] = ref
            staged = prepare(store, second, second_proposal)
            target = vault / "concepts/local-storage.md"
            target.write_text(target.read_text() + "\nConcurrent editor change.\n")
            try:
                apply(store, second, staged["review_token"], "synthetic-fixture", adapter)
            except Conflict:
                pass
            else:
                raise AssertionError("Concurrent edit was not protected")
            assert "Concurrent editor change." in target.read_text()
            lint = json.loads(adapter.run(["lint", str(vault), "--json"]))
            assert not lint["findings"]["snapshot_mismatch"], lint["findings"]["snapshot_mismatch"]
            assert not lint["findings"]["broken_links"]
            print(
                json.dumps(
                    {
                        "integration": "pass",
                        "adapter": compatibility,
                        "checks": [
                            "capture",
                            "proposal",
                            "review",
                            "publish",
                            "replay",
                            "source_delta",
                            "manifest_origin_and_snapshot",
                            "index",
                            "todo",
                            "log_deduplication",
                            "concurrent_edit_protection",
                            "snapshot_consistency",
                            "resolved_links",
                        ],
                        "real_vault_touched": False,
                        "human_semantic_pilot": "not run",
                    },
                    indent=2,
                )
            )
        finally:
            store.close()


if __name__ == "__main__":
    main()
