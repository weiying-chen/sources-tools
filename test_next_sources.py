import unittest

from next_sources import Boundary, Episode, WorkflowIndex, next_episodes


class NextSourcesTests(unittest.TestCase):
    def test_returns_next_three_after_master_boundary(self):
        episodes = [
            Episode("2026-07-03", "Newest title", "https://youtu.be/newest1", "newest1", 0),
            Episode("2026-07-02", "Second newest", "https://youtu.be/second1", "second1", 1),
            Episode("2026-07-01", "Top master title", "https://youtu.be/master1", "master1", 2),
            Episode("2026-06-30", "Old gap", "", "", 3),
        ]
        selected = next_episodes(
            episodes, Boundary("Top master title", "master1"), WorkflowIndex(set(), set()), 3
        )

        self.assertEqual([episode.title for episode in selected], ["Second newest", "Newest title"])

    def test_skips_a_newer_episode_already_in_workflow(self):
        episodes = [
            Episode("2026-07-03", "Newest title", "", "", 0),
            Episode("2026-07-02", "Already queued", "", "queued1", 1),
            Episode("2026-07-01", "Next title", "", "", 2),
            Episode("2026-06-30", "Master title", "", "", 3),
        ]
        selected = next_episodes(
            episodes,
            Boundary("Master title", ""),
            WorkflowIndex({"queued1"}, set()),
            3,
        )

        self.assertEqual([episode.title for episode in selected], ["Next title", "Newest title"])

    def test_limit_defaults_are_applied_by_selection(self):
        episodes = [
            Episode(f"2026-07-0{day}", f"Title {day}", "", "", 4 - day)
            for day in range(1, 5)
        ]

        selected = next_episodes(
            episodes, Boundary("Title 1", ""), WorkflowIndex(set(), set()), 3
        )

        self.assertEqual([episode.title for episode in selected], ["Title 2", "Title 3", "Title 4"])


if __name__ == "__main__":
    unittest.main()
