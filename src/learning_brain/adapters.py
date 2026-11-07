from __future__ import annotations

import json
import subprocess

from .config import Config
from .errors import BrainError
from .fs import inside


class WikiAdapter:
    """Only documented CLI boundaries; no imports of private obsidian_wiki modules."""

    def __init__(self, config: Config):
        self.config = config

    def run(self, args: list[str], timeout=30) -> str:
        try:
            result = subprocess.run(
                [*self.config.wiki_command, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BrainError("obsidian-wiki is unavailable or timed out") from exc
        if result.returncode:
            # Do not print arbitrary subprocess output: it may contain private vault content.
            raise BrainError(f"obsidian-wiki {args[0]} failed (exit {result.returncode})")
        return result.stdout

    def preflight(self) -> dict:
        version = self.run(["--version"]).strip()
        # Behavior contract tested against this release, not a claim about future compatibility.
        if version != "obsidian-wiki 2026.10.2":
            raise BrainError(f"Unsupported adapter version: {version}; tested: 2026.10.2")
        # The CLI writes shared service paths too; reject linked parents before invoking it.
        for relative in (
            ".manifest.json",
            ".manifest.lock",
            ".memory.lock",
            "index.md",
            "log.md",
            "hot.md",
            "_meta/todos.md",
            "_meta/profile.md",
            "_meta/.memory-adopted",
        ):
            inside(self.config.vault, relative)
        try:
            manifest = json.loads(inside(self.config.vault, ".manifest.json").read_text())
        except (OSError, ValueError) as exc:
            raise BrainError(
                "Vault manifest is missing or invalid; repair it before publishing"
            ) from exc
        if not isinstance(manifest, dict) or not isinstance(manifest.get("sources"), (dict, list)):
            raise BrainError("Vault manifest requires a sources mapping/list; nothing overwritten")
        status = json.loads(
            self.run(["memory", "status", "--vault", str(self.config.vault), "--json"])
        )
        if not isinstance(status, dict) or not status.get("migrated"):
            raise BrainError("Vault memory is not adopted; review memory migrate before applying")
        help_text = self.run(["cache-update", "--help"])
        if "--key" not in help_text or "--pages" not in help_text:
            raise BrainError("Adapter requires cache-update --key and --pages")
        return {"version": version, "memory_adopted": True}

    def finalize(self, bundle: dict) -> None:
        vault = self.config.vault
        snapshot = inside(vault, bundle["snapshot"]["path"])
        pages = [op["path"] for op in bundle["operations"]]
        # Origin first, archive second: cache-update may rekey a matching archive entry.
        self.run(
            [
                "cache-update",
                str(vault),
                str(snapshot),
                "--key",
                bundle["origin"],
                "--pages",
                *pages,
            ]
        )
        self.run(["cache-update", str(vault), str(snapshot), "--pages", *pages])
        for thread in bundle["open_threads"]:
            self.run(
                [
                    "memory",
                    "todo",
                    "add",
                    thread["text"],
                    "--origin",
                    thread["origin"],
                    "--vault",
                    str(vault),
                ]
            )
        log_path = inside(vault, "log.md")
        marker = f"operation_id={bundle['job_id']}"
        already_logged = log_path.exists() and marker in log_path.read_text()
        args = ["memory", "sync"]
        if not already_logged:
            args.extend(
                [
                    "INGEST",
                    marker,
                    "source=learning-brain",
                    f"pages_created={sum(op['expected'] is None for op in bundle['operations'])}",
                    f"pages_updated={sum(op['expected'] is not None for op in bundle['operations'])}",
                ]
            )
        self.run([*args, "--vault", str(vault)])

    def refresh_search(self) -> dict:
        if not self.config.qmd_command:
            return {"state": "disabled"}
        try:
            result = subprocess.run(
                [*self.config.qmd_command, "update"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"state": "pending", "reason": "QMD unavailable or timed out"}
        if result.returncode:
            return {"state": "pending", "reason": f"QMD exit {result.returncode}"}
        return {
            "state": "updated",
            "embeddings": "not refreshed; explicitly run qmd embed if needed",
        }
