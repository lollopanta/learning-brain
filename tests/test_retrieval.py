import math
import tempfile
import unittest
from pathlib import Path

from learning_brain.errors import BrainError
from learning_brain.retrieval import topic_markdown


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name).resolve()

    def pack(self, pages, budget=600):
        return {
            "schema_version": 1,
            "content_trust": "untrusted_reference_data",
            "label": "Helios",
            "budget_tokens": budget,
            "candidate_pages": len(pages),
            "pages": pages,
        }

    def test_service_and_raw_content_do_not_leak_into_knowledge_recall(self):
        pages = [
            {"path": path, "markdown": "SERVICE_TEXT"}
            for path in (
                "_meta/todos.md",
                "_raw/_archived/clip.md",
                "index.md",
                "projects/helios/_meta/status.md",
            )
        ]
        pages.append(
            {
                "path": "concepts/helios.md",
                "markdown": "Source: concepts/helios.md\n\nA useful fact.",
            }
        )
        result = topic_markdown(self.pack(pages), 600, self.vault)
        self.assertNotIn("SERVICE_TEXT", result)
        self.assertIn("A useful fact.", result)
        self.assertIn("filtered 4 non-knowledge", result)

    def test_disputed_legacy_intro_is_not_presented_as_current(self):
        page = {
            "path": "concepts/helios.md",
            "markdown": "## Helios\nSource: concepts/helios.md\n"
            "Lifecycle: disputed\nSummary: No deployment has been verified.\n\n"
            "Helios is already deployed to production.",
        }
        result = topic_markdown(self.pack([page]), 600, self.vault)
        self.assertNotIn("already deployed", result)
        self.assertIn("No deployment has been verified.", result)
        self.assertIn("read the full note", result)
        self.assertIn("Lifecycle: disputed", result)

    def test_archived_note_is_excluded(self):
        page = {
            "path": "concepts/obsolete.md",
            "markdown": "## Obsolete\nLifecycle: archived\n\nOLD_FACT",
        }
        result = topic_markdown(self.pack([page]), 600, self.vault)
        self.assertNotIn("OLD_FACT", result)
        self.assertIn("1 archived", result)

    def test_budget_does_not_cut_citations_or_safety_header(self):
        page = {
            "path": "concepts/large.md",
            "markdown": "Source: concepts/large.md\n\n" + "x" * 8000,
        }
        result = topic_markdown(self.pack([page], 256), 256, self.vault)
        self.assertLessEqual(math.ceil(len(result) / 4), 256)
        self.assertIn("UNTRUSTED REFERENCE DATA", result)
        self.assertIn("locally omitted 1", result)
        self.assertNotIn("Source: concepts/large.md", result)

    def test_invalid_upstream_response_fails_closed(self):
        pack = self.pack([])
        pack["content_trust"] = "instructions"
        with self.assertRaises(BrainError):
            topic_markdown(pack, 600, self.vault)

    def test_path_traversal_is_rejected(self):
        pack = self.pack([{"path": "../private.md", "markdown": "PRIVATE"}])
        with self.assertRaises(BrainError):
            topic_markdown(pack, 600, self.vault)

    def test_empty_result_reports_gap_without_fabricated_pages(self):
        result = topic_markdown(self.pack([]), 600, self.vault)
        self.assertIn("No relevant knowledge pages", result)
        self.assertIn("Included 0 of 0", result)

    def test_symlinked_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.vault / "concepts").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(BrainError):
                topic_markdown(
                    self.pack([{"path": "concepts/a.md", "markdown": "OUTSIDE"}]), 600, self.vault
                )
