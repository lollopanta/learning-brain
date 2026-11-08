"""Inject packaged skill instructions only; no runtime, vault, or transcript access."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = {"SessionStart", "SubagentStart", "UserPromptSubmit"}
MAX_INPUT = 1024 * 1024


def context(event):
    reminder = (
        "Learning Brain: use brain-recall for relevant prior decisions/project context; "
        "use brain-debrief when the user asks to preserve durable session learning. "
        "Do not run either workflow on unrelated prompts. Skill loading is not authorization "
        "to capture transcripts or publish notes. Keep evidence, uncertainty and review gates. "
        "Respect the user's current scope and permission mode. "
        "Subagents must return proposed findings to their parent, not publish independently."
    )
    if event == "UserPromptSubmit":
        return (
            reminder
            + " Read the applicable SKILL.md before use: "
            + "; ".join(
                str(ROOT / "skills" / name / "SKILL.md")
                for name in ("brain-recall", "brain-debrief")
            )
        )
    parts = [reminder, "Packaged Learning Brain skills (paths below are absolute):"]
    for name in ("brain-recall", "brain-debrief"):
        path = ROOT / "skills" / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        if len(text) > 24000:
            raise ValueError("Packaged skill exceeds bootstrap limit")
        parts.append(f"Skill file: {path}\nRelative references resolve from {path.parent}.\n{text}")
    return "\n\n".join(parts)


def main():
    try:
        raw = sys.stdin.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError("Hook input exceeds limit")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Hook input must be an object")
        event = payload.get("hook_event_name")
        if event not in EVENTS:
            print("{}")
            return
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": event,
                        "additionalContext": context(event),
                    }
                }
            )
        )
    except (OSError, ValueError, TypeError) as exc:
        # Do not block the user's turn, and do not leak input on failures.
        print("{}")
        print(f"Learning Brain skill bootstrap unavailable: {type(exc).__name__}", file=sys.stderr)


if __name__ == "__main__":
    main()
