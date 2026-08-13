from pm_docx_utils import row_needs_english


def cell(*paragraphs: str) -> str:
    return "<w:tc>" + "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs
    ) + "</w:tc>"


def test_legacy_row_with_english_is_not_missing() -> None:
    assert not row_needs_english(
        cell("5分鐘足球運動", "Leg Endurance Workout", "English description.")
    )


def test_modern_row_with_only_url_is_missing() -> None:
    assert row_needs_english(cell("中文標題", "https://youtu.be/example"))


def test_modern_row_with_url_and_english_is_not_missing() -> None:
    assert not row_needs_english(
        cell("中文標題", "https://youtu.be/example", "Easy Fitness - Title", "Description.")
    )


def test_modern_timestamp_does_not_count_as_english() -> None:
    assert row_needs_english(
        cell("中文標題", "https://youtu.be/example", "03:20-04:10 (50秒)")
    )


def test_parenthesized_production_note_does_not_count_as_english() -> None:
    assert row_needs_english(
        cell("中文標題", "https://youtu.be/example", "(24/10/1 health, 10/15下)")
    )


def test_parenthesized_note_before_english_is_not_missing() -> None:
    assert not row_needs_english(
        cell(
            "中文標題",
            "https://youtu.be/example",
            "(24/10/1 health, 10/15下)",
            "English title",
            "English description.",
        )
    )


def test_legacy_parenthesized_note_before_english_is_not_missing() -> None:
    assert not row_needs_english(
        cell(
            "5分鐘毛巾操運動 活化手腕關節",
            "(25/10/29 health)",
            "Towel Workout for Stronger Wrists",
            "English description.",
        )
    )


def test_note_and_title_without_description_is_missing() -> None:
    assert row_needs_english(
        cell("中文標題", "(25/10/29 health)", "English title")
    )
