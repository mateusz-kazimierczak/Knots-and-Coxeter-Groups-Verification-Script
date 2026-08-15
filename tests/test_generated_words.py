from __future__ import annotations

from collections import Counter
import csv
from pathlib import Path
import unittest


DATA = Path(__file__).parents[1] / "data" / "generated_words"


class GeneratedWordDataTests(unittest.TestCase):
    def test_combined_csv_matches_preserved_source_files(self) -> None:
        source_paths = {
            "breadth_first_search": DATA / "raw" / "order_three_bfs.txt",
            "randomized_depth_first_search": (
                DATA / "raw" / "order_three_randomized_dfs.txt"
            ),
        }
        source_words = {
            origin: [
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            for origin, path in source_paths.items()
        }

        with (DATA / "order_three_candidates.csv").open(
            encoding="utf-8", newline=""
        ) as input_file:
            rows = list(csv.DictReader(input_file))

        self.assertEqual(len(rows), 20_074)
        self.assertEqual(len({row["word"] for row in rows}), 20_073)
        self.assertEqual(
            [int(row["full_length"]) for row in rows],
            sorted(int(row["full_length"]) for row in rows),
        )

        observed_counts: Counter[tuple[str, int]] = Counter()
        for row in rows:
            origin = row["origin_program"]
            source_line = int(row["source_line"])
            word = row["word"]
            self.assertEqual(word, source_words[origin][source_line - 1])
            self.assertEqual(word, word[: len(word) // 3] * 3)
            self.assertEqual(int(row["repeat_count"]), 3)
            self.assertEqual(int(row["piece_length"]) * 3, len(word))
            self.assertEqual(int(row["full_length"]), len(word))
            observed_counts[(origin, len(word))] += 1

        self.assertEqual(
            observed_counts,
            Counter(
                {
                    ("breadth_first_search", 6): 4,
                    ("breadth_first_search", 12): 20,
                    ("breadth_first_search", 18): 156,
                    ("breadth_first_search", 24): 536,
                    ("breadth_first_search", 30): 3_340,
                    ("breadth_first_search", 36): 14_799,
                    ("randomized_depth_first_search", 24): 1,
                    ("randomized_depth_first_search", 36): 1,
                    ("randomized_depth_first_search", 42): 3,
                    ("randomized_depth_first_search", 48): 11,
                    ("randomized_depth_first_search", 54): 121,
                    ("randomized_depth_first_search", 60): 1_082,
                }
            ),
        )

    def test_through_length_42_snapshots_are_complete(self) -> None:
        pairs = (
            ("order_three_bfs.txt", "order_three_bfs.txt"),
            ("order_three_randomized_dfs.txt", "order_three_dfs.txt"),
        )
        for raw_name, snapshot_name in pairs:
            with self.subTest(snapshot=snapshot_name):
                raw_words = [
                    line.strip()
                    for line in (DATA / "raw" / raw_name)
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]
                snapshot_words = [
                    line.strip()
                    for line in (DATA / "through_length_42" / snapshot_name)
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]
                self.assertEqual(
                    snapshot_words,
                    [word for word in raw_words if len(word) <= 42],
                )


if __name__ == "__main__":
    unittest.main()
