from __future__ import annotations

from itertools import product
import random
import unittest

from coxeter_knot_checker.core import evaluate_word
from coxeter_knot_checker.tightening import (
    AFFINE_A3_REWRITES,
    AFFINE_A3_TETRAHEDRON,
    AFFINE_B3_GEOMETRY,
    STANDARD_REWRITES,
    STANDARD_TETRAHEDRON,
    cancel_involutions,
    generate_order_three_dfs,
    tighten_word,
    word_to_lattice_directions,
)


class TighteningTests(unittest.TestCase):
    def test_tetrahedron_reflections_are_exact_involutions(self) -> None:
        for letter in "ABCD":
            with self.subTest(letter=letter):
                reflected_twice = STANDARD_TETRAHEDRON.reflect_word(letter * 2)
                self.assertEqual(reflected_twice, STANDARD_TETRAHEDRON)

    def test_core_geometry_matches_original_b3_tetrahedron(self) -> None:
        for length in range(1, 5):
            for letters in product("ABCD", repeat=length):
                word = "".join(letters)
                with self.subTest(word=word):
                    self.assertEqual(
                        AFFINE_B3_GEOMETRY.has_simple_centre_path(word),
                        STANDARD_TETRAHEDRON.has_simple_centre_path(word),
                    )

    def test_affine_a3_rewrites_match_the_a3_tetrahedron(self) -> None:
        for left, right in AFFINE_A3_REWRITES.equivalent_rewrites:
            with self.subTest(left=left, right=right):
                self.assertEqual(
                    AFFINE_A3_TETRAHEDRON.reflect_word(left),
                    AFFINE_A3_TETRAHEDRON.reflect_word(right),
                )

    def test_short_dfs_finds_the_four_order_three_words(self) -> None:
        results = generate_order_three_dfs(2, rng=random.Random(7))
        self.assertEqual(
            set(results),
            {"ACACAC", "BCBCBC", "CACACA", "CBCBCB"},
        )

    def test_standard_rewrites_preserve_the_affine_map(self) -> None:
        relations = (
            STANDARD_REWRITES.equivalent_rewrites
            + STANDARD_REWRITES.contractions
        )
        for left, right in relations:
            with self.subTest(left=left, right=right):
                self.assertEqual(evaluate_word(left), evaluate_word(right))

    def test_advanced_tightening_uses_a_length_reducing_relation(self) -> None:
        original = "ACAC"
        tightened = tighten_word(
            original,
            passes=1,
            attempts_per_pass=1,
            rng=random.Random(0),
        )
        self.assertEqual(len(tightened), 2)
        # A cyclic rotation conjugates the element, so exact maps can differ;
        # finite order is the invariant needed for the repeated gallery.
        self.assertEqual(
            evaluate_word(tightened).order(),
            evaluate_word(original).order(),
        )
        self.assertTrue(STANDARD_TETRAHEDRON.has_simple_centre_path(tightened))

    def test_adjacent_involutions_cancel_to_stability(self) -> None:
        self.assertEqual(cancel_involutions("ABBA"), "")
        self.assertEqual(cancel_involutions("ABBAC"), "C")

    def test_first_d_reflection_converts_without_index_error(self) -> None:
        self.assertEqual(word_to_lattice_directions("D"), "d")


if __name__ == "__main__":
    unittest.main()
