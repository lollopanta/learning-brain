"""Bridge the hook protocol to the registered runtime with a bounded deadline."""

import json
import subprocess
import sys
from pathlib import Path


def main():
    payload = {}
    try:
        raw = sys.stdin.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError("Input too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Input must be an object")
        runner = Path(__file__).resolve().parents[1] / "scripts/run.py"
        result = subprocess.run(
            [sys.executable, str(runner), "automation-hook"],
            input=raw,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode:
            raise ValueError("Runtime unavailable")
        output = json.loads(result.stdout)
        if not isinstance(output, dict):
            raise ValueError("Invalid runtime response")
        if payload.get("hook_event_name") in ("Stop", "SessionEnd"):
            # Enforce the UX contract even if a runtime regression returns a continuation.
            if output:
                print(
                    "Learning Brain tail output suppressed; inspect runtime diagnostics.",
                    file=sys.stderr,
                )
            print("{}")
            return
        print(json.dumps(output))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        if isinstance(payload, dict) and payload.get("hook_event_name") in ("Stop", "SessionEnd"):
            print("Learning Brain capture deferred; inspect runtime diagnostics.", file=sys.stderr)
            print("{}")
            return
        print(
            json.dumps(
                {"systemMessage": "Learning Brain automation unavailable; use manual debrief."}
            )
        )


if __name__ == "__main__":
    main()
