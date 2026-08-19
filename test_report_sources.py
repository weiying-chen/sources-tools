import tempfile
import unittest
from pathlib import Path

from report_sources import count_documents, count_programme


class FolderReportTests(unittest.TestCase):
    def test_counts_only_documents_directly_in_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "one.docx").touch()
            (folder / "two.DOC").touch()
            (folder / "image.png").touch()
            (folder / "~$temporary.docx").touch()
            (folder / "download.docx:Zone.Identifier").touch()
            nested = folder / "ok"
            nested.mkdir()
            (nested / "finished.docx").touch()

            self.assertEqual(count_documents(folder), 2)

    def test_programme_uses_queued_and_translated(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            queued = project / "queued"
            translated = project / "translated"
            queued.mkdir()
            translated.mkdir()
            (queued / "a.docx").touch()
            (queued / "b.docx").touch()
            (translated / "c.docx").touch()

            self.assertEqual(count_programme(project), (2, 1))


if __name__ == "__main__":
    unittest.main()
