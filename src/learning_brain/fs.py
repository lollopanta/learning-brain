from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
from pathlib import Path, PurePosixPath

from .errors import BrainError


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def revision(path: Path) -> str | None:
    if path.exists() and not path.is_file():
        raise BrainError(f"Expected a regular file: {path}")
    return digest(path.read_bytes()) if path.exists() else None


def inside(root: Path, relative: str) -> Path:
    """Only portable relative paths; refuse every symlink component, even internal ones."""
    rel = PurePosixPath(relative)
    if (
        not relative
        or rel.is_absolute()
        or ".." in rel.parts
        or "\\" in relative
        or str(rel) != relative
        or any(ord(c) < 32 for c in relative)
    ):
        raise BrainError(f"Invalid relative path: {relative!r}")
    target = root
    for part in rel.parts:
        target = target / part
        if target.is_symlink():
            raise BrainError(f"Symlink component refused: {relative}")
    if root.resolve() not in target.resolve().parents:
        raise BrainError(f"Path escapes root: {relative}")
    return target


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".learning-brain-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name)


@contextlib.contextmanager
def writer_lock(path: Path):
    """POSIX lock released by the kernel on process death; never steal stale files."""
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BrainError("Another Learning Brain publisher holds the vault lock") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)
