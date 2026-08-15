"""Experimental gallery generation and Coxeter-word tightening.

This module contains the exploratory algorithms that originally lived in a
notebook.  It is intentionally separate from :mod:`coxeter_knot_checker.core`:
``core`` verifies a finished gallery, while this module searches for galleries
and rewrites their words.

All geometric calculations use exact integers or :class:`fractions.Fraction`.
In particular, collision decisions do not depend on floating-point rounding.
Importing this module has no side effects; searches only run when one of the
public functions is called.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import random
from typing import Protocol, Sequence, TextIO

from .core import BASE_CENTRE, LETTERS, gallery_points, parse_word

Scalar = int | Fraction
Point = tuple[Fraction, Fraction, Fraction]


def _point(values: Sequence[Scalar]) -> Point:
    """Convert a three-dimensional point to exact rational coordinates."""
    if len(values) != 3:
        raise ValueError("a point must have exactly three coordinates")
    return tuple(Fraction(value) for value in values)  # type: ignore[return-value]


def _add(left: Point, right: Point) -> Point:
    return tuple(left[i] + right[i] for i in range(3))  # type: ignore[return-value]


def _subtract(left: Point, right: Point) -> Point:
    return tuple(left[i] - right[i] for i in range(3))  # type: ignore[return-value]


def _scale(value: Fraction, vector: Point) -> Point:
    return tuple(value * coordinate for coordinate in vector)  # type: ignore[return-value]


def _dot(left: Point, right: Point) -> Fraction:
    return sum((left[i] * right[i] for i in range(3)), start=Fraction(0))


def _cross(left: Point, right: Point) -> Point:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _normalise_generated_word(word: str) -> str:
    """Validate a generated word while allowing the empty reduced word."""
    if not word:
        return ""
    return parse_word(word)


def _centres_are_simple(centres: Sequence[tuple[Scalar, Scalar, Scalar]]) -> bool:
    """Check for repeated centres, allowing only a final return to the start."""
    seen = {centres[0]}
    final_index = len(centres) - 1
    for index, centre in enumerate(centres[1:], start=1):
        if centre in seen:
            return index == final_index and centre == centres[0]
        seen.add(centre)
    return True


class CentrePathGeometry(Protocol):
    """Geometry operations required by generation and tightening algorithms."""

    def has_simple_centre_path(self, word: str) -> bool: ...

    def closes_without_centre_clash(self, word: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class CoreB3Geometry:
    """Use the canonical affine B~3 model implemented in :mod:`.core`."""

    def centre_path(self, word: str) -> tuple[Point, ...]:
        if not word:
            return (_point(BASE_CENTRE),)
        return tuple(_point(point) for point in gallery_points(word))

    def has_simple_centre_path(self, word: str) -> bool:
        return _centres_are_simple(self.centre_path(word))

    def closes_without_centre_clash(self, word: str) -> bool:
        if not word:
            return False
        centres = self.centre_path(word)
        return centres[-1] == centres[0] and _centres_are_simple(centres)


@dataclass(frozen=True, slots=True)
class Tetrahedron:
    """A tetrahedral chamber whose vertices are labelled ``A`` through ``D``.

    Reflecting at a label mirrors that vertex in the face opposite it.  The
    resulting tetrahedron is the adjacent chamber across that face.
    """

    A: Point
    B: Point
    C: Point
    D: Point

    def __post_init__(self) -> None:
        # Also makes direct construction with integer lists/NumPy arrays safe.
        object.__setattr__(self, "A", _point(self.A))
        object.__setattr__(self, "B", _point(self.B))
        object.__setattr__(self, "C", _point(self.C))
        object.__setattr__(self, "D", _point(self.D))

    @classmethod
    def from_vertices(
        cls,
        A: Sequence[Scalar],
        B: Sequence[Scalar],
        C: Sequence[Scalar],
        D: Sequence[Scalar],
    ) -> "Tetrahedron":
        return cls(_point(A), _point(B), _point(C), _point(D))

    @property
    def vertices(self) -> tuple[Point, Point, Point, Point]:
        return self.A, self.B, self.C, self.D

    @property
    def centre(self) -> Point:
        total = (Fraction(0), Fraction(0), Fraction(0))
        for vertex in self.vertices:
            total = _add(total, vertex)
        return _scale(Fraction(1, 4), total)

    def center(self) -> Point:
        """US-spelling compatibility helper for the original notebook code."""
        return self.centre

    def get_plot_points(self) -> list[Point]:
        """Return the four vertices in label order for plotting code."""
        return list(self.vertices)

    def reflect(self, vertex: str) -> "Tetrahedron":
        """Return the adjacent chamber obtained by reflecting one vertex."""
        label = vertex.upper()
        if label not in LETTERS or len(label) != 1:
            raise ValueError(f"invalid vertex {vertex!r}; expected A, B, C, or D")

        index = LETTERS.index(label)
        vertices = list(self.vertices)
        opposite_face = [point for i, point in enumerate(vertices) if i != index]
        face_origin, face_b, face_c = opposite_face
        normal = _cross(
            _subtract(face_b, face_origin),
            _subtract(face_c, face_origin),
        )
        squared_length = _dot(normal, normal)
        if squared_length == 0:
            raise ValueError("cannot reflect across a degenerate face")

        displacement = _subtract(vertices[index], face_origin)
        factor = 2 * _dot(displacement, normal) / squared_length
        vertices[index] = _subtract(vertices[index], _scale(factor, normal))
        return Tetrahedron(*vertices)

    def reflect_word(self, word: str) -> "Tetrahedron":
        """Apply every reflection in ``word`` and return the final chamber."""
        chamber = self
        for letter in parse_word(word):
            chamber = chamber.reflect(letter)
        return chamber

    def centre_path(self, word: str) -> tuple[Point, ...]:
        """Return chamber centres, including both the initial and final one."""
        parsed = _normalise_generated_word(word)
        chamber = self
        centres = [chamber.centre]
        for letter in parsed:
            chamber = chamber.reflect(letter)
            centres.append(chamber.centre)
        return tuple(centres)

    def has_simple_centre_path(self, word: str) -> bool:
        """Whether centres are distinct, apart from a final return to the start."""
        return _centres_are_simple(self.centre_path(word))

    def closes_without_centre_clash(self, word: str) -> bool:
        """Whether a nonempty word returns to its first centre only at the end."""
        if not word:
            return False
        centres = self.centre_path(word)
        return centres[-1] == centres[0] and self.has_simple_centre_path(word)

    def center_clash(self, word: str, *_compatibility_arguments: object) -> bool:
        """Compatibility wrapper returning whether the centre path is simple."""
        return self.has_simple_centre_path(word)

    def does_it_close(self, word: str, *_compatibility_arguments: object) -> bool:
        """Compatibility wrapper for the notebook's closure predicate."""
        return self.closes_without_centre_clash(word)

    def convert_back(self, word: str) -> str:
        """Compatibility wrapper for the lattice-direction encoding."""
        return word_to_lattice_directions(word, chamber=self)


# Original B~3 tetrahedron, retained for notebook compatibility and direction
# conversion.  Standard path checks use ``AFFINE_B3_GEOMETRY`` below.
STANDARD_TETRAHEDRON = Tetrahedron.from_vertices(
    (1, -1, -1),
    (1, 1, -1),
    (0, 0, -1),
    (0, 0, 0),
)

# Standard searches delegate to core.py's canonical affine B~3 geometry.
AFFINE_B3_GEOMETRY = CoreB3Geometry()

# Chamber realization for the affine A~3 relation system.  Its Coxeter orders
# are m(AB) = m(CD) = 2 and m(AC) = m(AD) = m(BC) = m(BD) = 3.
AFFINE_A3_TETRAHEDRON = Tetrahedron.from_vertices(
    (0, -1, 1),
    (0, 1, 1),
    (-1, 0, 0),
    (-1, 0, 2),
)


def _open_output(path: str | Path | None) -> TextIO | None:
    if path is None:
        return None
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return output.open("w", encoding="utf-8")


def _record(word: str, results: list[str], output: TextIO | None, echo: bool) -> None:
    results.append(word)
    if output is not None:
        output.write(f"{word}\n")
    if echo:
        print(word)


def generate_order_three_dfs(
    max_piece_length: int = 12,
    *,
    rng: random.Random | None = None,
    output_path: str | Path | None = None,
    echo: bool = False,
    geometry: CentrePathGeometry = AFFINE_B3_GEOMETRY,
) -> list[str]:
    """Find centre-simple words ``piece**3`` by randomized depth-first search.

    Only even piece lengths are tested, matching the original experiment.
    Randomness changes traversal order, not the set of results.  Pass a seeded
    :class:`random.Random` instance when reproducible ordering is important.
    """
    if max_piece_length < 1:
        return []

    generator = rng if rng is not None else random.Random()
    stack = list(LETTERS)
    results: list[str] = []
    output = _open_output(output_path)
    try:
        while stack:
            piece = stack.pop()
            if not geometry.has_simple_centre_path(piece):
                continue

            full_word = piece * 3
            if (
                len(piece) % 2 == 0
                and geometry.closes_without_centre_clash(full_word)
            ):
                _record(full_word, results, output, echo)

            if len(piece) < max_piece_length:
                offset = generator.randrange(len(LETTERS))
                for index in range(len(LETTERS)):
                    stack.append(piece + LETTERS[(offset + index) % len(LETTERS)])
    finally:
        if output is not None:
            output.close()
    return results


def generate_order_six_bfs(
    max_piece_length: int = 10,
    *,
    output_path: str | Path | None = None,
    echo: bool = False,
    geometry: CentrePathGeometry = AFFINE_B3_GEOMETRY,
) -> list[str]:
    """Find centre-simple words ``piece**6`` by breadth-first search."""
    if max_piece_length < 1:
        return []

    queue = deque(LETTERS)
    results: list[str] = []
    output = _open_output(output_path)
    try:
        while queue:
            piece = queue.popleft()
            full_word = piece * 6
            if geometry.closes_without_centre_clash(full_word):
                _record(full_word, results, output, echo)

            if len(piece) < max_piece_length:
                queue.extend(piece + letter for letter in LETTERS)
    finally:
        if output is not None:
            output.close()
    return results


@dataclass(frozen=True, slots=True)
class RewriteSystem:
    """Directed Coxeter rewrites used by a tightening strategy."""

    equivalent_rewrites: tuple[tuple[str, str], ...]
    contractions: tuple[tuple[str, str], ...] = ()


STANDARD_REWRITES = RewriteSystem(
    equivalent_rewrites=(
        ("AB", "BA"),
        ("AD", "DA"),
        ("BD", "DB"),
        ("ACA", "CAC"),
        ("BCB", "CBC"),
        ("CDCD", "DCDC"),
        ("BA", "AB"),
        ("DA", "AD"),
        ("DB", "BD"),
        ("CAC", "ACA"),
        ("DCDC", "CDCD"),
    ),
    contractions=(
        ("BAB", "A"),
        ("ABA", "B"),
        ("DAD", "A"),
        ("ADA", "D"),
        ("DBD", "B"),
        ("BDB", "D"),
        ("ACAC", "CA"),
        ("CACA", "AC"),
        ("BCBC", "CB"),
        ("CBCB", "BC"),
        ("DCDCD", "CDC"),
        ("CDCDC", "DCD"),
    ),
)

AFFINE_A3_REWRITES = RewriteSystem(
    equivalent_rewrites=(
        ("AB", "BA"),
        ("ACA", "CAC"),
        ("BCB", "CBC"),
        ("DC", "CD"),
        ("ADA", "DAD"),
        ("BDB", "DBD"),
        ("BA", "AB"),
        ("CAC", "ACA"),
        ("CBC", "BCB"),
        ("CD", "DC"),
        ("DAD", "ADA"),
        ("DBD", "BDB"),
    )
)


def cancel_involutions(word: str) -> str:
    """Remove adjacent ``AA``, ``BB``, ``CC``, and ``DD`` pairs to stability."""
    reduced: list[str] = []
    for letter in _normalise_generated_word(word):
        if reduced and reduced[-1] == letter:
            reduced.pop()
        else:
            reduced.append(letter)
    return "".join(reduced)


def rotate_word(word: str, offset: int) -> str:
    """Return the cyclic rotation beginning at ``offset``."""
    if not word:
        return word
    index = offset % len(word)
    return word[index:] + word[:index]


def _replace_first(word: str, old: str, new: str) -> str | None:
    index = word.find(old)
    if index == -1:
        return None
    return word[:index] + new + word[index + len(old) :]


def _accept_if_simple(
    current: str,
    candidate: str | None,
    geometry: CentrePathGeometry,
) -> str:
    if candidate is None or not geometry.has_simple_centre_path(candidate):
        return current
    return candidate


def tighten_word(
    word: str,
    *,
    passes: int = 10,
    attempts_per_pass: int = 250,
    rng: random.Random | None = None,
    geometry: CentrePathGeometry = AFFINE_B3_GEOMETRY,
    rules: RewriteSystem = STANDARD_REWRITES,
) -> str:
    """Shorten a word using contractions and randomized Coxeter rewrites.

    Each proposed word is accepted only when its chamber-centre path remains
    simple.  Contractions are tried deterministically; one randomly selected
    equal-length rewrite is then used to expose new contractions.  A cyclic
    rotation at the beginning of each pass allows reductions across the old
    word boundary.
    """
    if passes < 0 or attempts_per_pass < 0:
        raise ValueError("passes and attempts_per_pass must be non-negative")

    current = parse_word(word)
    generator = rng if rng is not None else random.Random()
    for _ in range(passes):
        if not current:
            break
        current = rotate_word(current, generator.randrange(len(current)))
        for _ in range(attempts_per_pass):
            for long_form, short_form in rules.contractions:
                candidate = _replace_first(current, long_form, short_form)
                current = _accept_if_simple(current, candidate, geometry)

            if not current or not rules.equivalent_rewrites:
                continue
            old, new = generator.choice(rules.equivalent_rewrites)
            candidate = _replace_first(current, old, new)
            if candidate is not None:
                candidate = cancel_involutions(candidate)
            current = _accept_if_simple(current, candidate, geometry)
    return current


def tighten_word_locally(
    word: str,
    *,
    passes: int = 10,
    anchors_per_pass: int = 50,
    attempts_per_anchor: int = 50,
    window_radius: int = 10,
    rng: random.Random | None = None,
    geometry: CentrePathGeometry = AFFINE_B3_GEOMETRY,
    rules: RewriteSystem = STANDARD_REWRITES,
) -> str:
    """Apply randomized equivalent rewrites near several local anchor points.

    This is the cleaned version of the two older ``go_smaller_*`` routines.
    It does not contract long braid words; use :func:`tighten_word` for the
    newer, more aggressive reduction strategy.
    """
    if min(passes, anchors_per_pass, attempts_per_anchor, window_radius) < 0:
        raise ValueError("iteration counts and window_radius must be non-negative")

    current = parse_word(word)
    generator = rng if rng is not None else random.Random()
    for _ in range(passes):
        if not current:
            break
        current = rotate_word(current, generator.randrange(len(current)))
        for _ in range(anchors_per_pass):
            if not current or not rules.equivalent_rewrites:
                break
            anchor = generator.randrange(len(current))
            for _ in range(attempts_per_anchor):
                old, new = generator.choice(rules.equivalent_rewrites)
                left = max(0, anchor - window_radius)
                right = min(len(current), anchor + window_radius)
                relative_index = current[left:right].find(old)
                if relative_index == -1:
                    continue
                index = left + relative_index
                candidate = current[:index] + new + current[index + len(old) :]
                candidate = cancel_involutions(candidate)
                current = _accept_if_simple(current, candidate, geometry)
                anchor = min(anchor, max(0, len(current) - 1))
    return current


def word_to_lattice_directions(
    word: str,
    *,
    chamber: Tetrahedron = STANDARD_TETRAHEDRON,
) -> str:
    """Encode displacements at ``D`` reflections as ``f/b/r/l/u/d`` moves."""
    direction_by_delta = {
        (Fraction(1, 2), Fraction(0), Fraction(0)): "f",
        (Fraction(-1, 2), Fraction(0), Fraction(0)): "b",
        (Fraction(0), Fraction(1, 2), Fraction(0)): "r",
        (Fraction(0), Fraction(-1, 2), Fraction(0)): "l",
        (Fraction(0), Fraction(0), Fraction(1, 2)): "u",
        (Fraction(0), Fraction(0), Fraction(-1, 2)): "d",
    }

    result: list[str] = []
    current = chamber
    previous_centre = current.centre
    for letter in _normalise_generated_word(word):
        current = current.reflect(letter)
        centre = current.centre
        if letter == "D":
            delta = _subtract(centre, previous_centre)
            try:
                result.append(direction_by_delta[delta])
            except KeyError as error:
                raise ValueError(f"unexpected D-reflection displacement: {delta}") from error
        previous_centre = centre
    return "".join(result)


def letter_counts(word: str) -> tuple[int, int, int, int]:
    """Return the number of A, B, C, and D letters, in that order."""
    parsed = _normalise_generated_word(word)
    return tuple(parsed.count(letter) for letter in LETTERS)  # type: ignore[return-value]


# The short class name appeared throughout the exploratory notebooks.
Tetra = Tetrahedron


# Compatibility entry points for the names used in the original notebook.
def generate_seq_rand(
    max_piece_length: int = 12,
    *,
    rng: random.Random | None = None,
    output_path: str | Path | None = None,
    echo: bool = False,
) -> list[str]:
    return generate_order_three_dfs(
        max_piece_length,
        rng=rng,
        output_path=output_path,
        echo=echo,
    )


def generate_seq(
    max_piece_length: int = 10,
    *,
    output_path: str | Path | None = None,
    echo: bool = False,
) -> list[str]:
    return generate_order_six_bfs(
        max_piece_length,
        output_path=output_path,
        echo=echo,
    )


def go_smaller(word: str, **kwargs: object) -> str:
    return tighten_word(word, **kwargs)  # type: ignore[arg-type]


def go_smaller_seq(word: str, **kwargs: object) -> str:
    """Compatibility name for local tightening in the standard B~3 system."""
    return tighten_word_locally(
        word,
        geometry=AFFINE_B3_GEOMETRY,
        rules=STANDARD_REWRITES,
        **kwargs,  # type: ignore[arg-type]
    )


def tighten_affine_a3_word_locally(word: str, **kwargs: object) -> str:
    """Tighten using the affine A~3 chamber and its matching relations."""
    return tighten_word_locally(
        word,
        geometry=AFFINE_A3_TETRAHEDRON,
        rules=AFFINE_A3_REWRITES,
        **kwargs,  # type: ignore[arg-type]
    )


__all__ = [
    "AFFINE_A3_REWRITES",
    "AFFINE_A3_TETRAHEDRON",
    "AFFINE_B3_GEOMETRY",
    "CentrePathGeometry",
    "CoreB3Geometry",
    "RewriteSystem",
    "STANDARD_REWRITES",
    "STANDARD_TETRAHEDRON",
    "Tetra",
    "Tetrahedron",
    "cancel_involutions",
    "generate_order_six_bfs",
    "generate_order_three_dfs",
    "generate_seq",
    "generate_seq_rand",
    "go_smaller",
    "go_smaller_seq",
    "letter_counts",
    "rotate_word",
    "tighten_affine_a3_word_locally",
    "tighten_word",
    "tighten_word_locally",
    "word_to_lattice_directions",
]
