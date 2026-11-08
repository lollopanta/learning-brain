from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .errors import BrainError
from .fs import digest


@dataclass(frozen=True)
class Config:
    vault: Path
    state: Path
    source_roots: tuple[Path, ...]
    wiki_command: tuple[str, ...] = ("obsidian-wiki",)
    qmd_command: tuple[str, ...] = ()
    max_capture_bytes: int = 2_000_000
    automation: str = "off"

    def __post_init__(self):
        if self.automation not in ("off", "review"):
            raise BrainError("automation must be off or review")
        object.__setattr__(self, "vault", self.vault.expanduser().resolve())
        object.__setattr__(self, "state", self.state.expanduser().resolve())
        object.__setattr__(
            self, "source_roots", tuple(root.expanduser().resolve() for root in self.source_roots)
        )
        if (
            self.state == self.vault
            or self.vault in self.state.parents
            or self.state in self.vault.parents
        ):
            raise BrainError("state_dir must be a dedicated directory outside the vault")

    @property
    def vault_id(self) -> str:
        return digest(str(self.vault).encode())[:24]


def load(path: Path) -> Config:
    path = path.expanduser().resolve()
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    allowed = {
        "vault",
        "state_dir",
        "source_roots",
        "wiki_command",
        "qmd_command",
        "max_capture_bytes",
        "automation",
    }
    if set(data) - allowed:
        raise BrainError(f"Unknown config keys: {sorted(set(data) - allowed)}")

    def resolve(value):
        if not isinstance(value, str) or not value.strip():
            raise BrainError("Paths must be non-empty strings")
        p = Path(value).expanduser()
        return (p if p.is_absolute() else path.parent / p).resolve()

    vault = resolve(data.get("vault"))
    if not vault.is_dir():
        raise BrainError(f"Vault does not exist: {vault}")
    state = resolve(
        data.get(
            "state_dir",
            str(
                Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
                / "learning-brain"
                / digest(str(vault).encode())[:24]
            ),
        )
    )
    if state == vault or vault in state.parents:
        raise BrainError("state_dir must be outside the vault")
    roots = data.get("source_roots", [])
    if not isinstance(roots, list) or not roots:
        raise BrainError("Configure at least one explicit source_roots directory")
    roots = tuple(resolve(root) for root in roots)
    if any(not root.is_dir() for root in roots):
        raise BrainError("Every source_roots entry must be an existing directory")

    def command(key, default):
        value = data.get(key, default)
        if not isinstance(value, list) or not all(
            isinstance(arg, str) and arg.strip() for arg in value
        ):
            raise BrainError(f"{key} must be an argv array, never shell text")
        return tuple(value)

    wiki = command("wiki_command", ["obsidian-wiki"])
    if not wiki:
        raise BrainError("wiki_command must not be empty")
    limit = data.get("max_capture_bytes", 2_000_000)
    if type(limit) is not int or not 1024 <= limit <= 50_000_000:
        raise BrainError("max_capture_bytes must be an integer between 1024 and 50000000")
    return Config(
        vault, state, roots, wiki, command("qmd_command", []), limit, data.get("automation", "off")
    )
