from __future__ import annotations

import contextlib
import json
import os
import sqlite3
from datetime import UTC, datetime

from .config import Config
from .errors import BrainError


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Store:
    def __init__(self, config: Config):
        self.config = config
        config.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(config.state, 0o700)
        self.db = sqlite3.connect(config.state / "queue.sqlite", timeout=10)
        os.chmod(config.state / "queue.sqlite", 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.db.close()
            raise BrainError(f"Unsupported queue schema version: {version}")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY, path TEXT NOT NULL, offset INTEGER NOT NULL,
                prefix_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL, start INTEGER NOT NULL,
                end INTEGER NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
                bundle TEXT, review_token TEXT, approved_by TEXT,
                error TEXT, created TEXT NOT NULL, updated TEXT NOT NULL);
            PRAGMA user_version=1;
        """)
        identity = self.db.execute("SELECT value FROM metadata WHERE key='vault'").fetchone()
        if identity and identity[0] != str(config.vault):
            self.db.close()
            raise BrainError("This state directory belongs to a different vault")
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('vault', ?)", (str(config.vault),)
            )

    def close(self):
        self.db.close()

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def job(self, job_id: str) -> dict:
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise BrainError(f"Unknown job: {job_id}")
        result = dict(row)
        for key in ("payload", "bundle"):
            if result[key] is not None:
                result[key] = json.loads(result[key])
        return result

    def jobs(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT id,source_id,start,end,state,error,created,updated FROM jobs ORDER BY created,id"
        ).fetchall()
        return [dict(row) for row in rows]

    def skip(self, job_id: str, reason: str):
        if not reason.strip():
            raise BrainError("A skip needs a non-empty reason")
        with self.transaction():
            job = self.job(job_id)
            if job["state"] == "skipped":
                return
            if job["state"] not in ("queued", "staged"):
                raise BrainError("A publishing/published job cannot be skipped")
            self.db.execute(
                "UPDATE jobs SET state='skipped',error=?,updated=? WHERE id=?",
                (reason, now(), job_id),
            )
