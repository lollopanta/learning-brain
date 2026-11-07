"""Optional hook recorder: no LLM, transcript parsing, vault writes, or subprocesses."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .config import load
from .errors import BrainError
from .fs import atomic_write, digest
from .store import canonical


def record(config, event: dict) -> dict:
    if event.get("permission_mode") == "plan" or event.get("stop_hook_active"):
        return {"state": "skipped"}
    if event.get("hook_event_name") not in ("Stop", "SessionEnd"):
        raise BrainError("Only Stop and SessionEnd checkpoint events are supported")
    session = event.get("session_id")
    transcript = event.get("transcript_path")
    if not isinstance(session, str) or not session or not isinstance(transcript, str):
        raise BrainError("Hook input needs session_id and transcript_path")
    path = Path(transcript).expanduser().resolve()
    if not any(root in path.parents for root in config.source_roots):
        raise BrainError("Hook transcript outside configured source roots")
    request = {
        "session_id": session,
        "transcript_path": str(path),
        "turn_id": event.get("turn_id"),
        "hook_event_name": event["hook_event_name"],
    }
    encoded = canonical(request).encode()
    spool = config.state / "requests"
    spool.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(config.state, 0o700)
    target = spool / f"{digest(encoded)}.json"
    atomic_write(target, encoded)
    return {"state": "recorded"}


def main():
    # Hook protocol output remains valid even on failure; diagnostics go to stderr.
    try:
        config_path = os.environ.get("LEARNING_BRAIN_CONFIG")
        if not config_path:
            raise BrainError("Set LEARNING_BRAIN_CONFIG to an explicit TOML config")
        raw = sys.stdin.buffer.read(65_537)
        if len(raw) > 65_536:
            raise BrainError("Hook input exceeds 64 KiB")
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise BrainError("Hook input must be an object")
        record(load(Path(config_path)), event)
    except (BrainError, OSError, ValueError) as exc:
        print(f"learning-brain checkpoint not recorded: {type(exc).__name__}", file=sys.stderr)
    print("{}")
