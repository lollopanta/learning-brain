"""Read installed hook discovery via Codex itself; never trust hooks or start a model."""

import argparse
import json
import queue
import subprocess
import threading
import time
from pathlib import Path


def discover(cwd, executable="codex"):
    process = subprocess.Popen(
        [executable, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    messages = queue.Queue()

    def read():
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                continue
        messages.put({"closed": True})

    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    def request(identifier, method, params):
        process.stdin.write(
            json.dumps({"id": identifier, "method": method, "params": params}) + "\n"
        )
        process.stdin.flush()
        deadline = time.monotonic() + 20
        # Bound total time as well as notification count.
        for _ in range(200):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Codex {method} timed out")
            message = messages.get(timeout=remaining)
            if message.get("closed"):
                raise RuntimeError("Codex app-server closed before replying")
            if message.get("id") == identifier:
                if "error" in message:
                    raise RuntimeError(f"Codex {method} failed: {message['error']}")
                return message["result"]
        raise RuntimeError("Too many unrelated Codex notifications")

    try:
        request(
            1,
            "initialize",
            {
                "clientInfo": {"name": "learning_brain_check", "version": "0.1"},
                "capabilities": {"experimentalApi": True},
            },
        )
        process.stdin.write('{"method":"initialized"}\n')
        process.stdin.flush()
        return request(2, "hooks/list", {"cwds": [str(Path(cwd).resolve())]})
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=1)
        for pipe in (process.stdin, process.stdout):
            pipe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=str(Path.cwd()))
    parser.add_argument("--codex", default="codex")
    args = parser.parse_args()
    result = discover(args.cwd, args.codex)
    hooks = [
        hook
        for entry in result["data"]
        for hook in entry["hooks"]
        if hook.get("pluginId") == "learning-brain@learning-brain-local"
    ]
    expected = {"sessionStart", "subagentStart", "userPromptSubmit", "stop", "sessionEnd"}
    if len(hooks) != 7 or {hook["eventName"] for hook in hooks} != expected:
        raise SystemExit("FAIL: Codex did not discover the seven Learning Brain handlers")
    if any(not hook["enabled"] for hook in hooks):
        raise SystemExit("FAIL: a Learning Brain hook is disabled")
    print(
        json.dumps(
            {
                "codex_discovery": "pass",
                "hooks": [
                    {
                        key: hook.get(key)
                        for key in ("eventName", "pluginId", "enabled", "trustStatus")
                    }
                    for hook in hooks
                ],
                "model_started": False,
                "trust_modified": False,
                "automatic_delivery": "not tested",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
