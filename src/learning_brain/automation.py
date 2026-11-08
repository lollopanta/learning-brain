"""Opt-in local capture and one bounded maintenance continuation; never publishes."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .errors import BrainError
from .fs import writer_lock
from .sources import capture
from .store import Store

MARKER = "[learning-brain:auto-debrief:v1]"
EVENTS = {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"}
ROUTING = (
    "Learning Brain automation=review. Recall bounded relevant context when prior project "
    "decisions matter. Automatically prepare durable findings with brain-debrief when queued; "
    "no explicit save request is needed for preparation. Never auto-apply. Show one concise "
    "review batch with claims, sources and tokens; wait for authorization of those changes. "
    "Skip routine or already-covered learning. If the user excludes this session from memory, "
    "run automation-pause SESSION_ID before capture. Do not change the user's task or permission mode."
)


def value(store, key):
    row = store.db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def put(store, key, text):
    with store.db:
        store.db.execute("INSERT OR REPLACE INTO metadata VALUES (?,?)", (key, text))


def pause(config, session):
    if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session):
        raise BrainError("Invalid session id")
    store = Store(config)
    try:
        put(store, "auto:paused:" + session, "true")
    finally:
        store.close()
    return {"session_id": session, "automation": "paused", "existing_jobs": "preserved"}


def identity(config, event):
    session = event.get("session_id")
    if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session):
        raise BrainError("Invalid hook session id")
    raw = event.get("transcript_path")
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        raise BrainError("Hook needs an absolute transcript path")
    path = Path(raw).resolve(strict=True)
    if not path.is_file() or not any(root in path.parents for root in config.source_roots):
        raise BrainError("Hook transcript is outside configured source roots")
    with path.open("rb") as stream:
        header = json.loads(stream.readline(1_000_001))
    if (
        not isinstance(header, dict)
        or header.get("type") != "session_meta"
        or not isinstance(header.get("payload"), dict)
        or header["payload"].get("id") != session
    ):
        raise BrainError("Hook session does not match transcript identity")
    return session, path


def baseline(store, session, path):
    """Anchor a never-acquired session without copying its historical messages."""
    source = "agent:codex/" + session
    with store.transaction():
        previous = store.db.execute("SELECT path FROM sources WHERE id=?", (source,)).fetchone()
        if previous:
            if Path(previous["path"]).resolve() != path:
                raise BrainError("Session identity is already registered at a different path")
            return False
        h = hashlib.sha256()
        offset = 0
        with path.open("rb") as stream:
            # Bound total work; oversized history requires explicit manual acquisition.
            while line := stream.readline(store.config.max_capture_bytes + 1):
                if len(line) > store.config.max_capture_bytes or offset + len(line) > 50_000_000:
                    raise BrainError("Automatic baseline exceeds limits; use manual capture")
                if not line.endswith(b"\n"):
                    break
                h.update(line)
                offset += len(line)
        store.db.execute(
            "INSERT INTO sources VALUES (?,?,?,?)", (source, str(path), offset, h.hexdigest())
        )
        return True


def pending(store, session):
    rows = store.db.execute(
        "SELECT id,state FROM jobs WHERE source_id=? AND state IN ('queued','staged','publishing') "
        "ORDER BY created,id LIMIT 10",
        ("agent:codex/" + session,),
    ).fetchall()
    return [dict(row) for row in rows]


def handle(config, event):
    if not isinstance(event, dict):
        raise BrainError("Hook input must be an object")
    kind = event.get("hook_event_name")
    # SessionEnd may omit permission_mode. Do not infer permission to capture a plan session.
    if kind == "SessionEnd" and event.get("permission_mode") not in (
        "default",
        "acceptEdits",
        "dontAsk",
        "bypassPermissions",
    ):
        return {}
    if (
        config.automation != "review"
        or kind not in EVENTS
        or event.get("permission_mode") == "plan"
        or event.get("agent_id")
        or event.get("stop_hook_active")
    ):
        return {}
    session, path = identity(config, event)
    store = Store(config)
    try:
        with writer_lock(config.state / "automation.lock"):
            if value(store, "auto:paused:" + session):
                return {}
            anchored = baseline(store, session, path)
            if kind in ("SessionStart", "UserPromptSubmit"):
                jobs = pending(store, session)
                return {
                    "hookSpecificOutput": {
                        "hookEventName": kind,
                        "additionalContext": ROUTING
                        + " Session id: "
                        + session
                        + ". Pending jobs: "
                        + json.dumps(jobs),
                    }
                }
            # If startup was missed, establish a baseline rather than importing history.
            if anchored:
                return {
                    "systemMessage": "Learning Brain baseline established; automatic capture starts next turn."
                }
            if kind == "Stop":
                turn = event.get("turn_id")
                if not isinstance(turn, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", turn):
                    raise BrainError("Stop needs a valid turn_id for bounded continuation")
                if value(store, "auto:last_turn:" + session) == turn:
                    return {}
            result = capture(store, path)
            if kind == "SessionEnd":
                return {}  # Acquisition only; cannot start a model on SessionEnd.
            put(store, "auto:last_turn:" + session, turn)
            jobs = pending(store, session)
            queued = [job["id"] for job in jobs if job["state"] == "queued"]
            if not queued or result.get("state") != "queued":
                return {}
            return {
                "decision": "block",
                "reason": (
                    MARKER + " Automatic memory preparation, not a statement from the user. "
                    "Use the installed brain-debrief skill for session " + session + ". "
                    "Inspect these acquired jobs: " + json.dumps(queued) + ". "
                    "Prepare only durable, non-duplicate findings; skip jobs with no durable value. "
                    "If capture reports more_available, finish bounded acquisition before synthesis. "
                    "Do not create a competing update to a target already touched by a staged job: "
                    "leave that new job queued and report it as deferred until review. "
                    "Never cite this automatic request or maintenance replies as user evidence. "
                    "Run propose and review, then show one concise review batch; never apply here. "
                    "Do not capture again during this maintenance continuation. "
                    "Do not start another agent or change the user's task. "
                    "This is the only automatic continuation for this turn. "
                    + (
                        "More source data remains to acquire. "
                        if result.get("more_available")
                        else ""
                    )
                ),
            }
    finally:
        store.close()
