from update_sources import extract_english_title, matching_title_keys


def test_early_home_prefix_is_optional() -> None:
    final_title = "早點回家∣盧柏任ft.范宸菲∣提升記憶力這樣做"
    master_title = "盧柏任ft.范宸菲∣提升記憶力這樣做"

    assert matching_title_keys(final_title) == matching_title_keys(master_title)


def test_early_home_text_inside_title_is_not_removed() -> None:
    title = "運動後早點回家∣健康訓練"

    assert matching_title_keys(title)[0].startswith("運動後早點回家")


def test_extract_english_title_accepts_yt_title_label() -> None:
    paragraphs = [
        "建議YT標題",
        "All About Health - Regenerating Knee Cartilage",
        "YT標題",
        "Regenerating Knee Cartilage",
    ]

    assert extract_english_title(paragraphs) == "Regenerating Knee Cartilage"
