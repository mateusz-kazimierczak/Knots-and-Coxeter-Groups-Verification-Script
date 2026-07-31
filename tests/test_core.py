from __future__ import annotations

import unittest

from coxeter_knot_checker.core import (
    AffineMap,
    check_gallery,
    evaluate_word,
    segment_intersection,
)
from coxeter_knot_checker.paper_words import (
    THEOREM_3_LENGTH_40,
    THEOREM_3_SYMMETRIC_PIECE,
    THEOREM_5_STATED_LENGTHS,
    THEOREM_5_WORDS,
)


class CoreTests(unittest.TestCase):
    def test_generators_are_reflections(self) -> None:
        for letter in "ABCD":
            with self.subTest(letter=letter):
                self.assertEqual(evaluate_word(letter * 2), AffineMap.identity())

    def test_basic_coxeter_relations(self) -> None:
        for word in (
            "ABAB",
            "ACACAC",
            "ADAD",
            "BCBCBC",
            "BDBD",
            "CDCDCDCD",
        ):
            with self.subTest(word=word):
                self.assertEqual(evaluate_word(word), AffineMap.identity())

    def test_segment_crossing_is_detected_exactly(self) -> None:
        hit = segment_intersection((0, 0, 0), (2, 2, 0), (0, 2, 0), (2, 0, 0))
        self.assertEqual(hit.kind, "point")
        self.assertEqual(tuple(str(value) for value in hit.point or ()), ("1", "1", "0"))

    def test_theorem_3_examples_are_valid_polygonal_knots(self) -> None:
        symmetric = check_gallery(THEOREM_3_SYMMETRIC_PIECE, repeat=3)
        self.assertEqual(symmetric.piece_order, 3)
        self.assertTrue(symmetric.valid_knot)

        length_40 = check_gallery(THEOREM_3_LENGTH_40, repeat=1)
        self.assertEqual(length_40.piece_length, 40)
        self.assertEqual(length_40.piece_order, 1)
        self.assertTrue(length_40.valid_knot)

    def test_theorem_5_words_are_closed_and_embedded(self) -> None:
        for label, word in THEOREM_5_WORDS.items():
            with self.subTest(label=label):
                check = check_gallery(word, repeat=3)
                self.assertEqual(check.piece_length, THEOREM_5_STATED_LENGTHS[label])
                self.assertEqual(check.piece_order, 3)
                self.assertTrue(check.closed)
                self.assertFalse(check.repeated_chambers)
                self.assertFalse(check.repeated_points)
                self.assertFalse(check.intersections)
                self.assertTrue(check.valid_knot)


if __name__ == "__main__":
    unittest.main()
