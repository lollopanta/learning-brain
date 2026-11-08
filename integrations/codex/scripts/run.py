"""Locate the user-installed runtime without relying on the app's PATH or shell env."""

import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    settings = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    registration = settings / "learning-brain/runtime.json"
    try:
        data = json.loads(registration.read_text())
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("Unsupported runtime registration")
        executable = Path(data["executable"])
        config = Path(os.environ.get("LEARNING_BRAIN_CONFIG", data["config"]))
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError("Registered runtime executable is missing or not absolute")
        if not config.is_absolute() or not config.is_file():
            raise ValueError("Registered config is missing or not absolute")
        argv = [str(executable), "--config", str(config), *sys.argv[1:]]
        if sys.argv[1:] == ["automation-hook"]:
            raw = sys.stdin.read(1_048_577)
            if len(raw) > 1_048_576:
                raise ValueError("Hook input exceeds limit")
            event = json.loads(raw)
            timeout = 2 if event.get("hook_event_name") == "SessionEnd" else 8
            return subprocess.run(argv, input=raw, text=True, timeout=timeout).returncode
        return subprocess.call(argv)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(
            json.dumps(
                {
                    "error": f"Learning Brain runtime is unavailable: {exc}",
                    "registration": str(registration),
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
