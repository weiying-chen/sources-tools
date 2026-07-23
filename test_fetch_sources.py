import unittest

from fetch_sources import (
    _extract_last_easy_fitness_timestamp,
    extract_easy_fitness_description,
)


class EasyFitnessDescriptionTests(unittest.TestCase):
    def test_keeps_summary_heading_and_timestamps_only(self):
        description = """更多運動點這👉https://example.test

肚子總是瘦不下來嗎？每天花5分鐘動一動。

➯5分鐘動起來！
00:25 抱頭肘腿
02:05 C手抬腿
03:30 直划開合

大愛一台 播出時間
週一～週五 0630
"""
        self.assertEqual(
            extract_easy_fitness_description(description),
            "肚子總是瘦不下來嗎？每天花5分鐘動一動。\n\n"
            "➯5分鐘動起來！\n"
            "00:25 抱頭肘腿\n"
            "02:05 C手抬腿\n"
            "03:30 直划開合",
        )
        self.assertEqual(
            _extract_last_easy_fitness_timestamp(description),
            "03:30｜直划開合",
        )

    def test_leaves_unknown_description_unchanged(self):
        self.assertEqual(extract_easy_fitness_description("ordinary text\n"), "ordinary text")


if __name__ == "__main__":
    unittest.main()
