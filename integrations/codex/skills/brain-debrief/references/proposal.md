# Proposal schema v1

Create a JSON file outside the tracked repository when it contains real session data. The root
requires schema_version=1 and updates (0–5). open_threads is optional (0–5); at least one item
must exist. Unknown fields fail. Each update requires the fields in this example; related is
optional and contains existing or same-batch vault-relative .md paths.

```json
{
  "schema_version": 1,
  "updates": [{
    "path": "projects/example/concepts/storage.md",
    "expected_revision": null,
    "kind": "decision",
    "title": "Local storage decision",
    "summary": "SQLite is selected for one local writer.",
    "tags": ["storage"],
    "claims": [{
      "text": "SQLite is selected while the workflow has one local writer.",
      "epistemic": "user_stated",
      "evidence": [{"message_id": "b100-220", "quote": "Use SQLite for one local writer."}]
    }]
  }],
  "open_threads": [{
    "text": "Validate restart recovery",
    "origin": "projects/example/concepts/storage.md",
    "evidence": [{"message_id": "b220-330", "quote": "Next, validate restart recovery."}]
  }]
}
```

The IDs/quotes above illustrate shape only: replace them with actual inspected evidence.
For an existing target, expected_revision is the lowercase 64-character SHA-256 of its bytes.
The proposal renderer preserves existing body/metadata and adds evidence-linked content before
Sources. It does not delete obsolete claims. Do not promise automatic editorial consolidation.

Kinds: learning, decision, correction. Epistemic states: user_stated, assistant_reported,
inferred, unverified. Each claim needs 1–5 exact evidence references. A page needs 1–10 claims,
1–5 portable tags, a single-line title (160 characters max) and summary (200 max).
Claim text cannot contain wikilinks: use related for validated note links. No fabricated stubs
to meet a link quota. A user_stated claim needs user evidence; an open thread needs only direct
user evidence and an existing/proposed origin note.

No numeric confidence is accepted from the model. New notes start draft with a conservative
conventional prior. Changes to reviewed/verified notes invalidate that prior review; corrections
are disputed until reconciled. User review must check that quotes support the paraphrase,
that proposed plans are not presented as completed work, and that private excerpts are appropriate.

`propose JOB FILE` persists a bundle and token. `review JOB` returns complete diffs and selected
evidence. `apply JOB --review-token TOKEN --reviewer NAME` publishes only that bundle.
