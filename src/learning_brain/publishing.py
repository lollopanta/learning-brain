from __future__ import annotations

from .adapters import WikiAdapter
from .errors import BrainError, Conflict
from .fs import atomic_write, digest, inside, revision, writer_lock
from .sources import verify_source
from .store import Store, canonical, now


def apply(
    store: Store, job_id: str, token: str, reviewer: str, adapter=None, after_write=None
) -> dict:
    """Journaled, replayable publication. A multi-page batch is NOT globally atomic."""
    if not reviewer.strip() or len(reviewer) > 120 or any(ord(c) < 32 for c in reviewer):
        raise BrainError("A non-empty reviewer name is required")
    adapter = adapter or WikiAdapter(store.config)
    # Lock is vault-scoped even if two configurations use separate state directories.
    with writer_lock(inside(store.config.vault, ".learning-brain.lock")):
        job = store.job(job_id)
        bundle = job["bundle"]
        if (
            not bundle
            or token != job["review_token"]
            or token != digest(canonical(bundle).encode())
        ):
            raise BrainError("Review token does not match the current proposal")
        if bundle["vault_id"] != store.config.vault_id:
            raise BrainError("Proposal belongs to a different vault")
        if job["state"] == "published":
            return {"job_id": job_id, "state": "published", "replay": True}
        if job["state"] not in ("staged", "publishing"):
            raise BrainError("Only staged or interrupted publishing jobs can be applied")
        if job["state"] == "publishing" and job["approved_by"] != reviewer:
            raise BrainError("Recovery requires the original reviewer identity")
        verify_source(store, job)
        adapter.preflight()
        try:
            snapshot = bundle["snapshot"]
            writes = [
                {
                    "path": snapshot["path"],
                    "expected": None,
                    "after": snapshot["content"],
                    "sha256": snapshot["sha256"],
                },
                *bundle["operations"],
            ]
            # Preflight every target before any content writes. On recovery, desired bytes
            # may already exist. On first application, even identical preexisting bytes conflict.
            for write in writes:
                target = inside(store.config.vault, write["path"])
                current = revision(target)
                allowed = {write["expected"]}
                if job["state"] == "publishing":
                    allowed.add(write["sha256"])
                if current not in allowed:
                    raise Conflict(f"Changed since proposal: {write['path']}; nothing overwritten")
                if digest(write["after"].encode()) != write["sha256"]:
                    raise BrainError("Corrupt proposal bytes")
            # Commit the intent before the first filesystem mutation.
            with store.transaction():
                fresh = store.job(job_id)
                if fresh["review_token"] != token or fresh["state"] not in ("staged", "publishing"):
                    raise Conflict("Proposal changed while acquiring publication lock")
                store.db.execute(
                    "UPDATE jobs SET state='publishing',approved_by=?,error=NULL,updated=? WHERE id=?",
                    (reviewer, now(), job_id),
                )
            for write in writes:
                target = inside(store.config.vault, write["path"])
                current = revision(target)
                if current == write["sha256"]:
                    continue
                if current != write["expected"]:
                    raise Conflict(f"Concurrent write: {write['path']}; batch needs recovery")
                atomic_write(target, write["after"].encode())
                if after_write:
                    after_write(write["path"])
            adapter.finalize(bundle)
            with store.transaction():
                store.db.execute(
                    "UPDATE jobs SET state='published',error=NULL,updated=? WHERE id=?",
                    (now(), job_id),
                )
            return {
                "job_id": job_id,
                "state": "published",
                "pages": len(bundle["operations"]),
                "search": "run refresh once after the batch",
            }
        except Exception as exc:
            with store.transaction():
                store.db.execute(
                    "UPDATE jobs SET error=?,updated=? WHERE id=?", (str(exc), now(), job_id)
                )
            raise
