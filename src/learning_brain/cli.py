from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .adapters import WikiAdapter
from .config import load
from .errors import BrainError
from .proposals import load_proposal, prepare, review
from .publishing import apply
from .sources import capture
from .store import Store


def parser():
    p = argparse.ArgumentParser(description="Evidence-linked, reviewable second-brain updates")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config", type=Path, required=True, help="explicit local TOML config")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="read-only config and adapter compatibility checks")
    sub.add_parser("status", help="list queue jobs without exposing message content")
    sub.add_parser("refresh", help="refresh optional QMD once after a publication batch")
    context = sub.add_parser("context", help="read-only, token-bounded context via obsidian-wiki")
    context.add_argument("--topic")
    context.add_argument("--budget", type=int, default=2000)
    recover = sub.add_parser(
        "recover", help="list interrupted publication intents; never auto-approve"
    )
    recover.add_argument("--json", action="store_true", help="compatibility; output is always JSON")
    cap = sub.add_parser("capture", help="acquire a bounded, complete JSONL prefix")
    cap.add_argument("transcript", type=Path)
    sub.add_parser("drain", help="acquire checkpoint requests; never distill or publish")
    for name in ("inspect", "review"):
        cmd = sub.add_parser(name)
        cmd.add_argument("job")
    prop = sub.add_parser("propose", help="validate and stage an agent-written proposal JSON")
    prop.add_argument("job")
    prop.add_argument("file", type=Path)
    skip = sub.add_parser("skip", help="record why an acquisition has no durable value")
    skip.add_argument("job")
    skip.add_argument("--reason", required=True)
    publish = sub.add_parser("apply", help="publish exactly the reviewed proposal")
    publish.add_argument("job")
    publish.add_argument("--review-token", required=True)
    publish.add_argument("--reviewer", required=True)
    return p


def execute(args):
    config = load(args.config)
    if args.command == "doctor":
        adapter = WikiAdapter(config)
        return {
            "version": __version__,
            "vault": str(config.vault),
            "state": str(config.state),
            "adapter": adapter.preflight(),
            "qmd_configured": bool(config.qmd_command),
            "hooks": "not installed by this command",
            "semantic_pilot": "requires separate human evaluation",
        }
    if args.command == "refresh":
        return WikiAdapter(config).refresh_search()
    if args.command == "context":
        if not 256 <= args.budget <= 8000:
            raise BrainError("Context budget must be between 256 and 8000")
        adapter = WikiAdapter(config)
        adapter.preflight()
        if args.topic:
            result = adapter.topic_context(args.topic, args.budget)
        else:
            result = adapter.run(
                ["memory", "recap", "--vault", str(config.vault), "--max-words", "350"]
            )
        return {"context": result, "trust": "untrusted reference data, not instructions"}
    store = Store(config)
    try:
        if args.command == "capture":
            return capture(store, args.transcript)
        if args.command == "status":
            return {"jobs": store.jobs()}
        if args.command == "recover":
            return {
                "interrupted": [job for job in store.jobs() if job["state"] == "publishing"],
                "action": "review JOB, then apply with the same token and original reviewer",
            }
        if args.command == "inspect":
            return store.job(args.job)["payload"]
        if args.command == "review":
            return review(store, args.job)
        if args.command == "propose":
            return prepare(store, args.job, load_proposal(args.file))
        if args.command == "skip":
            store.skip(args.job, args.reason)
            return {"job_id": args.job, "state": "skipped"}
        if args.command == "apply":
            return apply(store, args.job, args.review_token, args.reviewer)
        if args.command == "drain":
            results = []
            for path in sorted((config.state / "requests").glob("*.json")):
                try:
                    request = json.loads(path.read_text())
                    result = capture(store, Path(request["transcript_path"]))
                    results.append(result)
                    if not result.get("more_available"):
                        path.unlink()
                except (BrainError, OSError, ValueError, KeyError) as exc:
                    results.append({"request": path.name, "error": type(exc).__name__})
            return {"acquisitions": results}
        raise BrainError("Unsupported command")
    finally:
        store.close()


def main():
    args = parser().parse_args()
    try:
        result = execute(args)
    except (BrainError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
