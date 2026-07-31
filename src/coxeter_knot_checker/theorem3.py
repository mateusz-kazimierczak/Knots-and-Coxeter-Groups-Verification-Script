"""Exhaustive-search extension for the symmetric part of Theorem 3.

The extension deliberately stops before knot-type identification.  It follows
only the search and simplification stages described in the paper:

1. enumerate short A/B/C/D pieces;
2. discard immediate backtracking, repeated chambers, odd D parity, words that
   are not of order three, and repeated/self-intersecting full galleries;
3. identify copies that differ only by the starting point or orientation; and
4. simplify the polygon by deleting a middle vertex whenever the triangle
   spanned by three consecutive vertices is disjoint from the rest of the
   polygon.

Candidates that do not simplify to a triangle are written out for visual
inspection.  This module does not name or classify their knot types.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import dataclass
from fractions import Fraction
import json
import multiprocessing
import os
from pathlib import Path
from typing import Iterable, Sequence

from .core import (
    BASE_CENTRE,
    GENERATORS,
    Point3,
    check_gallery,
    gallery_points,
)

LETTERS = "ABCD"


# ---------------------------------------------------------------------------
# Fast exact state engine used only by the exhaustive enumeration.
# It is the same signed-permutation affine model as in core.py, represented by
# integer tuples so that millions of short prefixes can be visited fast.
# ---------------------------------------------------------------------------

Linear = tuple[int, int, int, int, int, int]
State = tuple[int, int, int, int]  # linear-state id, translation x, y, z

IDENTITY_LINEAR: Linear = (0, 1, 2, 1, 1, 1)
GENERATOR_LINEAR: tuple[Linear, ...] = tuple(
    generator.permutation + generator.signs for generator in GENERATORS.values()
)
GENERATOR_SHIFT: tuple[Point3, ...] = tuple(
    generator.shift for generator in GENERATORS.values()
)


def _compose_linear(left: Linear, right: Linear) -> Linear:
    left_perm, left_signs = left[:3], left[3:]
    right_perm, right_signs = right[:3], right[3:]
    permutation = tuple(right_perm[left_perm[i]] for i in range(3))
    signs = tuple(
        left_signs[i] * right_signs[left_perm[i]] for i in range(3)
    )
    return permutation + signs  # type: ignore[return-value]


def _build_tables() -> tuple[
    tuple[Linear, ...],
    dict[Linear, int],
    tuple[tuple[tuple[int, Point3], ...], ...],
    tuple[Point3, ...],
]:
    linear_states: list[Linear] = []
    linear_ids: dict[Linear, int] = {}
    stack = [IDENTITY_LINEAR]
    while stack:
        state = stack.pop()
        if state in linear_ids:
            continue
        linear_ids[state] = len(linear_states)
        linear_states.append(state)
        for generator in GENERATOR_LINEAR:
            stack.append(_compose_linear(state, generator))

    transitions: list[list[tuple[int, Point3]]] = [
        [(-1, (0, 0, 0)) for _ in range(4)] for _ in linear_states
    ]
    moved_centres: list[Point3] = []
    for state_id, linear in enumerate(linear_states):
        permutation, signs = linear[:3], linear[3:]
        moved_centres.append(
            tuple(
                signs[i] * BASE_CENTRE[permutation[i]] for i in range(3)
            )  # type: ignore[arg-type]
        )
        for generator_id, generator_linear in enumerate(GENERATOR_LINEAR):
            target = linear_ids[_compose_linear(linear, generator_linear)]
            generator_shift = GENERATOR_SHIFT[generator_id]
            moved_shift = tuple(
                signs[i] * generator_shift[permutation[i]] for i in range(3)
            )
            transitions[state_id][generator_id] = (target, moved_shift)  # type: ignore[assignment]

    return (
        tuple(linear_states),
        linear_ids,
        tuple(tuple(row) for row in transitions),
        tuple(moved_centres),
    )


LINEAR_STATES, LINEAR_IDS, TRANSITIONS, MOVED_CENTRES = _build_tables()
IDENTITY: State = (LINEAR_IDS[IDENTITY_LINEAR], 0, 0, 0)


def _advance(state: State, generator_id: int) -> State:
    linear_id, x, y, z = state
    target, moved = TRANSITIONS[linear_id][generator_id]
    return target, x + moved[0], y + moved[1], z + moved[2]


def _centre(state: State) -> Point3:
    linear_id, x, y, z = state
    moved = MOVED_CENTRES[linear_id]
    return moved[0] + x, moved[1] + y, moved[2] + z


def _compose_state(left: State, right: State) -> State:
    left_linear_id, x, y, z = left
    right_linear_id, u, v, w = right
    linear = LINEAR_STATES[left_linear_id]
    permutation, signs = linear[:3], linear[3:]
    right_shift = (u, v, w)
    target_linear = LINEAR_IDS[
        _compose_linear(linear, LINEAR_STATES[right_linear_id])
    ]
    moved = tuple(
        signs[i] * right_shift[permutation[i]] for i in range(3)
    )
    return target_linear, x + moved[0], y + moved[1], z + moved[2]


def _third_power(state: State) -> State:
    return _compose_state(_compose_state(state, state), state)


def _full_path_has_distinct_centres(word: Sequence[int]) -> bool:
    state = IDENTITY
    seen = {_centre(state)}
    total_steps = 3 * len(word)
    step = 0
    for _ in range(3):
        for generator_id in word:
            state = _advance(state, generator_id)
            step += 1
            point = _centre(state)
            if step == total_steps and state == IDENTITY:
                continue
            if point in seen:
                return False
            seen.add(point)
    return state == IDENTITY


def cyclic_shifts(word: str) -> tuple[str, ...]:
    return tuple(word[index:] + word[:index] for index in range(len(word)))


def canonical_piece(word: str) -> str:
    """Choose one spelling up to starting point and traversal direction."""
    variants = list(cyclic_shifts(word))
    variants.extend(cyclic_shifts(word[::-1]))
    return min(variants)


@dataclass(frozen=True, slots=True)
class Enumeration:
    piece_length: int
    raw_candidates: tuple[str, ...]
    unique_candidates: tuple[str, ...]


def enumerate_pieces(piece_length: int) -> Enumeration:
    """Enumerate all centre-simple order-three pieces of one length."""
    if piece_length < 1:
        return Enumeration(piece_length, (), ())

    word: list[int] = []
    seen_centres = {_centre(IDENTITY)}
    candidates: list[str] = []

    def visit(depth: int, state: State, previous: int, d_count: int) -> None:
        if depth == piece_length:
            # Across the copy boundary, equal letters immediately backtrack.
            if word[0] == word[-1]:
                return
            # The paper's cube-parity condition.
            if d_count % 2:
                return
            # We need exact order three, not the identity.
            if state == IDENTITY or _third_power(state) != IDENTITY:
                return
            if _full_path_has_distinct_centres(word):
                candidates.append("".join(LETTERS[index] for index in word))
            return

        for generator_id in range(4):
            # XX crosses a face and immediately crosses back.
            if generator_id == previous:
                continue
            new_state = _advance(state, generator_id)
            point = _centre(new_state)
            if point in seen_centres:
                continue
            seen_centres.add(point)
            word.append(generator_id)
            visit(
                depth + 1,
                new_state,
                generator_id,
                d_count + (1 if generator_id == 3 else 0),
            )
            word.pop()
            seen_centres.remove(point)

    visit(0, IDENTITY, -1, 0)
    raw = tuple(sorted(candidates))
    unique = tuple(sorted({canonical_piece(candidate) for candidate in raw}))
    return Enumeration(piece_length, raw, unique)


# ---------------------------------------------------------------------------
# Empty-triangle simplification.
# ---------------------------------------------------------------------------


def _sub(a: Sequence[int | Fraction], b: Sequence[int | Fraction]) -> tuple:
    return tuple(a[i] - b[i] for i in range(3))


def _dot(a: Sequence[int | Fraction], b: Sequence[int | Fraction]):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a: Sequence[int | Fraction], b: Sequence[int | Fraction]) -> tuple:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _drop(point: Sequence[int | Fraction], coordinate: int) -> tuple:
    return tuple(point[i] for i in range(3) if i != coordinate)


def _orient2(a: Sequence, b: Sequence, c: Sequence):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_in_triangle_2d(point: Sequence, a: Sequence, b: Sequence, c: Sequence) -> bool:
    values = (_orient2(a, b, point), _orient2(b, c, point), _orient2(c, a, point))
    return all(value >= 0 for value in values) or all(value <= 0 for value in values)


def _in_unit_interval(value: Fraction) -> bool:
    return Fraction(0) <= value <= Fraction(1)


def _segment_intersection_2d(a: Sequence, b: Sequence, c: Sequence, d: Sequence):
    ux, uy = b[0] - a[0], b[1] - a[1]
    vx, vy = d[0] - c[0], d[1] - c[1]
    dx, dy = c[0] - a[0], c[1] - a[1]
    denominator = ux * vy - uy * vx
    if denominator:
        t = Fraction(dx * vy - dy * vx, denominator)
        s = Fraction(dx * uy - dy * ux, denominator)
        if _in_unit_interval(t) and _in_unit_interval(s):
            return "point", (Fraction(a[0]) + t * ux, Fraction(a[1]) + t * uy)
        return "none", None
    if dx * uy - dy * ux:
        return "none", None
    if ux == 0 and uy == 0:
        return ("point", tuple(Fraction(value) for value in a)) if tuple(a) in (tuple(c), tuple(d)) else ("none", None)
    axis = 0 if ux else 1
    component = (ux, uy)[axis]
    tc = Fraction(c[axis] - a[axis], component)
    td = Fraction(d[axis] - a[axis], component)
    lo = max(Fraction(0), min(tc, td))
    hi = min(Fraction(1), max(tc, td))
    if lo > hi:
        return "none", None
    if lo == hi:
        return "point", (Fraction(a[0]) + lo * ux, Fraction(a[1]) + lo * uy)
    return "overlap", None


def _segment_hits_triangle(
    p: Point3,
    q: Point3,
    a: Point3,
    b: Point3,
    c: Point3,
    allowed_points: Iterable[Point3] = (),
) -> bool:
    normal = _cross(_sub(b, a), _sub(c, a))
    if normal == (0, 0, 0):
        return True

    side_p = _dot(normal, _sub(p, a))
    side_q = _dot(normal, _sub(q, a))
    coordinate = max(range(3), key=lambda index: abs(normal[index]))
    aa, bb, cc = _drop(a, coordinate), _drop(b, coordinate), _drop(c, coordinate)
    allowed_3d = {tuple(Fraction(value) for value in point) for point in allowed_points}
    allowed_2d = {_drop(point, coordinate) for point in allowed_points}

    if side_p == 0 and side_q == 0:
        pp, qq = _drop(p, coordinate), _drop(q, coordinate)
        for point in (pp, qq):
            if _point_in_triangle_2d(point, aa, bb, cc) and point not in allowed_2d:
                return True
        for edge_start, edge_end in ((aa, bb), (bb, cc), (cc, aa)):
            kind, value = _segment_intersection_2d(pp, qq, edge_start, edge_end)
            if kind == "overlap":
                return True
            if kind == "point" and value not in allowed_2d:
                return True
        return False

    if (side_p > 0 and side_q > 0) or (side_p < 0 and side_q < 0):
        return False
    if side_p == side_q:
        return False

    t = Fraction(side_p, side_p - side_q)
    if not _in_unit_interval(t):
        return False
    point = tuple(Fraction(p[i]) + t * (q[i] - p[i]) for i in range(3))
    projected = _drop(point, coordinate)
    return _point_in_triangle_2d(projected, aa, bb, cc) and point not in allowed_3d


def _removable(points: Sequence[Point3], index: int) -> bool:
    n = len(points)
    if n <= 3:
        return False
    a = points[(index - 1) % n]
    b = points[index]
    c = points[(index + 1) % n]

    normal = _cross(_sub(b, a), _sub(c, a))
    if normal == (0, 0, 0):
        # Remove a straight subdivision, but not a reversal/spike.
        ab = _sub(b, a)
        bc = _sub(c, b)
        return _cross(ab, bc) == (0, 0, 0) and _dot(ab, bc) > 0

    for edge_index in range(n):
        if edge_index in ((index - 1) % n, index):
            continue
        p = points[edge_index]
        q = points[(edge_index + 1) % n]
        allowed: list[Point3] = []
        if p == a or q == a:
            allowed.append(a)
        if p == c or q == c:
            allowed.append(c)
        if _segment_hits_triangle(p, q, a, b, c, allowed):
            return False
    return True


@dataclass(frozen=True, slots=True)
class Simplification:
    initial_vertices: int
    removed_vertices: tuple[Point3, ...]
    final_points: tuple[Point3, ...]

    @property
    def final_vertices(self) -> int:
        return len(self.final_points)

    @property
    def simplified_to_triangle(self) -> bool:
        return self.final_vertices <= 3


def simplify_polygon(points: Sequence[Point3]) -> Simplification:
    """Repeatedly remove the first available empty-triangle vertex."""
    current = list(points)
    removed: list[Point3] = []
    changed = True
    while len(current) > 3 and changed:
        changed = False
        for index in range(len(current)):
            if _removable(current, index):
                removed.append(current[index])
                current.pop(index)
                changed = True
                break
    return Simplification(len(points), tuple(removed), tuple(current))


@dataclass(frozen=True, slots=True)
class CandidateResult:
    piece_length: int
    word: str
    valid_knot: bool
    simplification: Simplification | None
    failure: str | None = None

    @property
    def needs_visual_inspection(self) -> bool:
        return (
            self.valid_knot
            and self.simplification is not None
            and not self.simplification.simplified_to_triangle
        )


def _check_and_simplify(task: tuple[int, str]) -> CandidateResult:
    piece_length, word = task
    check = check_gallery(word, repeat=3)
    if not check.valid_knot:
        return CandidateResult(
            piece_length,
            word,
            False,
            None,
            "failed closure or embeddedness check",
        )
    simplification = simplify_polygon(check.points)
    return CandidateResult(piece_length, word, True, simplification)


@dataclass(frozen=True, slots=True)
class LengthResult:
    enumeration: Enumeration
    candidates: tuple[CandidateResult, ...]

    @property
    def valid_candidates(self) -> tuple[CandidateResult, ...]:
        return tuple(candidate for candidate in self.candidates if candidate.valid_knot)

    @property
    def simplified_count(self) -> int:
        return sum(
            candidate.simplification is not None
            and candidate.simplification.simplified_to_triangle
            for candidate in self.valid_candidates
        )

    @property
    def remaining(self) -> tuple[CandidateResult, ...]:
        return tuple(
            candidate for candidate in self.valid_candidates if candidate.needs_visual_inspection
        )

    def summary(self) -> dict[str, object]:
        return {
            "piece_length": self.enumeration.piece_length,
            "raw_candidates": len(self.enumeration.raw_candidates),
            "unique_candidates": len(self.enumeration.unique_candidates),
            "valid_unique_candidates": len(self.valid_candidates),
            "simplified_to_triangle": self.simplified_count,
            "remaining_for_visual_inspection": len(self.remaining),
        }


def run_search(
    max_length: int = 14,
    output_dir: str | Path | None = None,
    workers: int | None = None,
) -> dict[str, object]:
    """Run the full pruning/simplification search through ``max_length``."""
    if max_length < 1:
        raise ValueError("max_length must be positive")
    if workers is None:
        workers = min(8, os.cpu_count() or 1)
    if workers < 1:
        raise ValueError("workers must be positive")

    enumerations = [enumerate_pieces(length) for length in range(1, max_length + 1)]
    tasks = [
        (enumeration.piece_length, word)
        for enumeration in enumerations
        for word in enumeration.unique_candidates
    ]

    if workers == 1:
        candidate_results = list(map(_check_and_simplify, tasks))
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=multiprocessing.get_context("spawn"),
        ) as executor:
            candidate_results = list(
                executor.map(_check_and_simplify, tasks, chunksize=20)
            )

    by_length: dict[int, list[CandidateResult]] = {
        length: [] for length in range(1, max_length + 1)
    }
    for candidate in candidate_results:
        by_length[candidate.piece_length].append(candidate)

    length_results = [
        LengthResult(
            enumeration,
            tuple(sorted(by_length[enumeration.piece_length], key=lambda item: item.word)),
        )
        for enumeration in enumerations
    ]

    remaining = [
        candidate
        for result in length_results
        for candidate in result.remaining
    ]

    report: dict[str, object] = {
        "scope": (
            "Theorem 3 exhaustive pruning and empty-triangle simplification only; "
            "remaining cases require visual inspection."
        ),
        "coordinate_scale": 4,
        "max_piece_length": max_length,
        "workers": workers,
        "lengths": [result.summary() for result in length_results],
        "remaining_for_visual_inspection": [
            {
                "piece_length": candidate.piece_length,
                "word": candidate.word,
                "final_vertex_count": candidate.simplification.final_vertices,
            }
            for candidate in remaining
            if candidate.simplification is not None
        ],
    }

    if output_dir is not None:
        write_search_results(length_results, Path(output_dir), report)
    return report


def write_search_results(
    length_results: Sequence[LengthResult],
    output_dir: Path,
    report: dict[str, object] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    if report is None:
        report = {
            "coordinate_scale": 4,
            "lengths": [result.summary() for result in length_results],
        }
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    all_remaining: list[CandidateResult] = []
    for result in length_results:
        length = result.enumeration.piece_length
        csv_path = output_dir / f"length_{length:02d}_candidates.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "word",
                    "valid_knot",
                    "initial_vertices",
                    "removed_vertices",
                    "final_vertices",
                    "result",
                ]
            )
            for candidate in result.candidates:
                simplification = candidate.simplification
                writer.writerow(
                    [
                        candidate.word,
                        candidate.valid_knot,
                        simplification.initial_vertices if simplification else "",
                        len(simplification.removed_vertices) if simplification else "",
                        simplification.final_vertices if simplification else "",
                        (
                            "simplified_to_triangle"
                            if simplification and simplification.simplified_to_triangle
                            else "visual_inspection"
                            if candidate.needs_visual_inspection
                            else candidate.failure or "failed"
                        ),
                    ]
                )
        all_remaining.extend(result.remaining)

    text_lines = [
        "Candidates left after exhaustive pruning and empty-triangle simplification.",
        "These words are intentionally left for visual inspection.",
        "",
        "piece_length  final_vertices  word",
    ]
    for candidate in all_remaining:
        assert candidate.simplification is not None
        text_lines.append(
            f"{candidate.piece_length:12d}  "
            f"{candidate.simplification.final_vertices:14d}  {candidate.word}"
        )
    (output_dir / "remaining_for_visual_inspection.txt").write_text(
        "\n".join(text_lines) + "\n", encoding="utf-8"
    )

    remaining_json: list[dict[str, object]] = []
    for candidate in all_remaining:
        assert candidate.simplification is not None
        check = check_gallery(candidate.word, repeat=3)
        remaining_json.append(
            {
                "piece_length": candidate.piece_length,
                "word": candidate.word,
                "full_length": 3 * candidate.piece_length,
                "full_points": [list(point) for point in check.points],
                "simplified_points": [
                    list(point) for point in candidate.simplification.final_points
                ],
                "final_vertex_count": candidate.simplification.final_vertices,
                "coordinate_scale": 4,
            }
        )
    (output_dir / "remaining_for_visual_inspection.json").write_text(
        json.dumps(remaining_json, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
