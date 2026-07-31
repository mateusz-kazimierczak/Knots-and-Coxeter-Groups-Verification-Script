from __future__ import annotations

import os
import unittest

from coxeter_knot_checker.core import check_gallery
from coxeter_knot_checker.paper_words import THEOREM_3_SYMMETRIC_PIECE
from coxeter_knot_checker.theorem3 import enumerate_pieces, run_search, simplify_polygon


class Theorem3SearchTests(unittest.TestCase):
    def test_short_enumeration_counts(self) -> None:
        length_2 = enumerate_pieces(2)
        self.assertEqual(len(length_2.raw_candidates), 4)
        self.assertEqual(len(length_2.unique_candidates), 2)

        length_4 = enumerate_pieces(4)
        self.assertEqual(len(length_4.raw_candidates), 20)
        self.assertEqual(len(length_4.unique_candidates), 5)

    def test_symmetric_example_survives_elementary_simplification(self) -> None:
        check = check_gallery(THEOREM_3_SYMMETRIC_PIECE, repeat=3)
        simplified = simplify_polygon(check.points)
        self.assertFalse(simplified.simplified_to_triangle)
        self.assertIn(simplified.final_vertices, (6, 7))

    @unittest.skipUnless(
        os.environ.get("RUN_FULL_SEARCH") == "1",
        "set RUN_FULL_SEARCH=1 to run the complete length-14 regression",
    )
    def test_full_length_14_regression(self) -> None:
        report = run_search(max_length=14, workers=min(8, os.cpu_count() or 1))
        rows = {row["piece_length"]: row for row in report["lengths"]}
        self.assertEqual(rows[12]["unique_candidates"], 895)
        self.assertEqual(rows[12]["remaining_for_visual_inspection"], 0)
        self.assertEqual(rows[14]["raw_candidates"], 156576)
        self.assertEqual(rows[14]["unique_candidates"], 5780)
        self.assertEqual(rows[14]["simplified_to_triangle"], 5762)
        self.assertEqual(rows[14]["remaining_for_visual_inspection"], 18)


if __name__ == "__main__":
    unittest.main()
