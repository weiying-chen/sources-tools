import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from report_sources import (
    count_documents,
    count_programme,
    format_translation_section,
    main,
)


class FolderReportTests(unittest.TestCase):
    def test_translation_section_with_one_empty_programme(self):
        self.assertEqual(
            format_translation_section(
                [("大愛醫生館", 0), ("大愛真健康", 3)], 3
            ),
            "待翻譯的節目：\n(我會再選3集大愛醫生館)\n3集大愛真健康",
        )

    def test_translation_section_with_both_empty(self):
        self.assertEqual(
            format_translation_section(
                [("大愛醫生館", 0), ("大愛真健康", 0)], 3
            ),
            "待翻譯的節目：\n無\n(我會再選3集大愛醫生館)\n(我會再選3集大愛真健康)",
        )

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

    @mock.patch("report_sources.subprocess.run")
    @mock.patch("report_sources.build_report", return_value="report text")
    def test_main_confirms_successful_clipboard_copy(self, _build_report, run_mock):
        output = io.StringIO()
        with mock.patch("sys.argv", ["report-sources"]), redirect_stdout(output):
            self.assertEqual(main(), 0)

        run_mock.assert_called_once_with(
            ["wl-copy"], input="report text", text=True, check=True
        )
        self.assertEqual(
            output.getvalue(),
            "report text\nSuccess: Report copied to clipboard\n",
        )


if __name__ == "__main__":
    unittest.main()
