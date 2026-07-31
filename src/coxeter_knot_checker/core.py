"""Exact-geometry utilities for galleries in the affine B~3 complex.

The paper encodes a gallery by a word in the four face reflections A, B, C, D.
This module does only the elementary checks needed to decide whether the
centreline of a repeated gallery is a valid polygonal knot:

* evaluate the Coxeter word exactly;
* construct the chamber-centre path;
* check closure;
* check that no vertex/chamber is revisited; and
* check that non-adjacent line segments do not meet.

All chamber-centre coordinates are multiplied by four.  This keeps every
calculation integral and avoids numerical tolerances.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import re
from typing import Iterable, Sequence

Point3 = tuple[int, int, int]
RationalPoint3 = tuple[Fraction, Fraction, Fraction]

LETTERS = "ABCD"
BASE_CENTRE: Point3 = (4, 2, 1)


@dataclass(frozen=True, slots=True)
class AffineMap:
    """An exact signed-permutation affine map in three dimensions.

    The linear part acts by

        output[i] = signs[i] * input[permutation[i]].

    This compact form is all that is needed for the four reflections in the
    B~3 tessellation.
    """

    permutation: tuple[int, int, int] = (0, 1, 2)
    signs: tuple[int, int, int] = (1, 1, 1)
    shift: Point3 = (0, 0, 0)

    def __post_init__(self) -> None:
        if sorted(self.permutation) != [0, 1, 2]:
            raise ValueError(f"not a permutation: {self.permutation}")
        if any(value not in (-1, 1) for value in self.signs):
            raise ValueError(f"signs must be +/-1: {self.signs}")
        if len(self.shift) != 3:
            raise ValueError("shift must have three coordinates")

    @classmethod
    def identity(cls) -> "AffineMap":
        return cls()

    def apply(self, point: Sequence[int]) -> Point3:
        if len(point) != 3:
            raise ValueError("point must have three coordinates")
        return tuple(
            self.signs[i] * int(point[self.permutation[i]]) + self.shift[i]
            for i in range(3)
        )  # type: ignore[return-value]

    def compose(self, other: "AffineMap") -> "AffineMap":
        """Return ``self o other``."""
        permutation = tuple(
            other.permutation[self.permutation[i]] for i in range(3)
        )
        signs = tuple(
            self.signs[i] * other.signs[self.permutation[i]] for i in range(3)
        )
        moved_shift = tuple(
            self.signs[i] * other.shift[self.permutation[i]] for i in range(3)
        )
        shift = tuple(moved_shift[i] + self.shift[i] for i in range(3))
        return AffineMap(permutation, signs, shift)  # type: ignore[arg-type]

    def power(self, exponent: int) -> "AffineMap":
        if exponent < 0:
            raise ValueError("negative powers are not needed by this package")
        result = AffineMap.identity()
        base = self
        n = exponent
        while n:
            if n & 1:
                result = result.compose(base)
            base = base.compose(base)
            n >>= 1
        return result

    def order(self, bound: int = 24) -> int | None:
        """Return the exact finite order, or ``None`` if not found by ``bound``."""
        current = AffineMap.identity()
        for n in range(1, bound + 1):
            current = current.compose(self)
            if current == AffineMap.identity():
                return n
        return None

    @property
    def determinant(self) -> int:
        inversions = sum(
            1
            for i in range(3)
            for j in range(i + 1, 3)
            if self.permutation[i] > self.permutation[j]
        )
        permutation_sign = -1 if inversions % 2 else 1
        return permutation_sign * self.signs[0] * self.signs[1] * self.signs[2]

    def matrix(self) -> tuple[tuple[int, int, int], ...]:
        rows: list[tuple[int, int, int]] = []
        for i in range(3):
            row = [0, 0, 0]
            row[self.permutation[i]] = self.signs[i]
            rows.append(tuple(row))
        return tuple(rows)

    def to_dict(self) -> dict[str, object]:
        return {
            "matrix": [list(row) for row in self.matrix()],
            "shift": list(self.shift),
            "determinant": self.determinant,
        }


# Reflections in the four faces of the base chamber.  The chamber centre is
# scaled by four, so the translation in A is (8, 8, 0).
GENERATORS: dict[str, AffineMap] = {
    "A": AffineMap((1, 0, 2), (-1, -1, 1), (8, 8, 0)),
    "B": AffineMap((1, 0, 2), (1, 1, 1), (0, 0, 0)),
    "C": AffineMap((0, 2, 1), (1, 1, 1), (0, 0, 0)),
    "D": AffineMap((0, 1, 2), (1, 1, -1), (0, 0, 0)),
}


def parse_word(value: str) -> str:
    """Remove ordinary separators and validate an A/B/C/D word."""
    cleaned = re.sub(r"[\s,;:_\-]+", "", value).upper()
    invalid = sorted(set(cleaned) - set(LETTERS))
    if invalid:
        raise ValueError(f"invalid letters {invalid}; expected only A, B, C, D")
    if not cleaned:
        raise ValueError("word may not be empty")
    return cleaned


def evaluate_word(word: str) -> AffineMap:
    current = AffineMap.identity()
    for letter in parse_word(word):
        current = current.compose(GENERATORS[letter])
    return current


def gallery_states(word: str, repeat: int = 1) -> list[AffineMap]:
    """Return the chamber maps, including the initial and final chamber."""
    if repeat < 1:
        raise ValueError("repeat must be positive")
    parsed = parse_word(word)
    current = AffineMap.identity()
    states = [current]
    for _ in range(repeat):
        for letter in parsed:
            current = current.compose(GENERATORS[letter])
            states.append(current)
    return states


def gallery_points(word: str, repeat: int = 1) -> list[Point3]:
    """Return scaled chamber centres, including the final point."""
    return [state.apply(BASE_CENTRE) for state in gallery_states(word, repeat)]


def _sub(a: Sequence[int | Fraction], b: Sequence[int | Fraction]) -> tuple:
    return tuple(a[i] - b[i] for i in range(3))


def _cross(a: Sequence[int | Fraction], b: Sequence[int | Fraction]) -> tuple:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _in_unit_interval(value: Fraction) -> bool:
    return Fraction(0) <= value <= Fraction(1)


def _boxes_overlap(p: Point3, q: Point3, r: Point3, s: Point3) -> bool:
    for axis in range(3):
        if max(p[axis], q[axis]) < min(r[axis], s[axis]):
            return False
        if max(r[axis], s[axis]) < min(p[axis], q[axis]):
            return False
    return True


@dataclass(frozen=True, slots=True)
class SegmentIntersection:
    kind: str  # "none", "point", or "overlap"
    point: RationalPoint3 | None = None

    @property
    def exists(self) -> bool:
        return self.kind != "none"


def segment_intersection(
    p: Point3, q: Point3, r: Point3, s: Point3
) -> SegmentIntersection:
    """Compute the exact intersection of two closed 3-dimensional segments."""
    if not _boxes_overlap(p, q, r, s):
        return SegmentIntersection("none")

    u = _sub(q, p)
    v = _sub(s, r)
    w = _sub(r, p)

    if u == (0, 0, 0) or v == (0, 0, 0):
        raise ValueError("zero-length segment")

    uv = _cross(u, v)
    if uv != (0, 0, 0):
        # Solve p + t u = r + lambda v using a non-singular coordinate pair.
        for i, j in ((0, 1), (0, 2), (1, 2)):
            denominator = v[i] * u[j] - u[i] * v[j]
            if denominator == 0:
                continue
            t = Fraction(v[i] * w[j] - w[i] * v[j], denominator)
            lam = Fraction(u[i] * w[j] - w[i] * u[j], denominator)
            if not (_in_unit_interval(t) and _in_unit_interval(lam)):
                return SegmentIntersection("none")
            x = tuple(Fraction(p[k]) + t * u[k] for k in range(3))
            y = tuple(Fraction(r[k]) + lam * v[k] for k in range(3))
            if x == y:
                return SegmentIntersection("point", x)  # type: ignore[arg-type]
            return SegmentIntersection("none")
        raise AssertionError("non-parallel vectors had no usable coordinate pair")

    # Parallel segments meet only when they are collinear.
    if _cross(w, u) != (0, 0, 0):
        return SegmentIntersection("none")
    axis = next(i for i, value in enumerate(u) if value != 0)
    t0 = Fraction(r[axis] - p[axis], u[axis])
    t1 = Fraction(s[axis] - p[axis], u[axis])
    lo = max(Fraction(0), min(t0, t1))
    hi = min(Fraction(1), max(t0, t1))
    if lo > hi:
        return SegmentIntersection("none")
    if lo < hi:
        return SegmentIntersection("overlap")
    point = tuple(Fraction(p[k]) + lo * u[k] for k in range(3))
    return SegmentIntersection("point", point)  # type: ignore[arg-type]


def polygon_intersections(points: Sequence[Point3]) -> list[dict[str, object]]:
    """List forbidden intersections between non-adjacent edges of a closed polygon.

    ``points`` must contain each polygon vertex exactly once; the first point is
    not repeated at the end.
    """
    n = len(points)
    intersections: list[dict[str, object]] = []
    for i in range(n):
        p, q = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            r, s = points[j], points[(j + 1) % n]
            hit = segment_intersection(p, q, r, s)
            if hit.exists:
                intersections.append(
                    {
                        "edge_1": i,
                        "edge_2": j,
                        "kind": hit.kind,
                        "point": (
                            [str(value) for value in hit.point]
                            if hit.point is not None
                            else None
                        ),
                    }
                )
    return intersections


@dataclass(frozen=True, slots=True)
class GalleryCheck:
    word: str
    repeat: int
    piece_length: int
    full_length: int
    piece_order: int | None
    piece_map: AffineMap
    full_map: AffineMap
    closed: bool
    repeated_chambers: tuple[tuple[int, int], ...]
    repeated_points: tuple[tuple[int, int, Point3], ...]
    intersections: tuple[dict[str, object], ...]
    points: tuple[Point3, ...]  # vertices once; final repeated point omitted

    @property
    def valid_knot(self) -> bool:
        """Whether the word traces a closed embedded polygonal curve."""
        return (
            self.full_length >= 3
            and self.closed
            and not self.repeated_chambers
            and not self.repeated_points
            and not self.intersections
        )

    def to_dict(self, include_points: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "word": self.word,
            "repeat": self.repeat,
            "piece_length": self.piece_length,
            "full_length": self.full_length,
            "piece_order": self.piece_order,
            "piece_map": self.piece_map.to_dict(),
            "full_map": self.full_map.to_dict(),
            "closed": self.closed,
            "repeated_chambers": [
                {"first": first, "second": second}
                for first, second in self.repeated_chambers
            ],
            "repeated_points": [
                {"first": first, "second": second, "point": list(point)}
                for first, second, point in self.repeated_points
            ],
            "segment_intersections": list(self.intersections),
            "valid_knot": self.valid_knot,
            "coordinate_scale": 4,
        }
        if include_points:
            result["points"] = [list(point) for point in self.points]
        return result


def _find_repeated_states(states: Sequence[AffineMap]) -> tuple[tuple[int, int], ...]:
    seen: dict[AffineMap, int] = {}
    repeats: list[tuple[int, int]] = []
    final = len(states) - 1
    for index, state in enumerate(states):
        if index == final and state == states[0]:
            continue
        if state in seen:
            repeats.append((seen[state], index))
        else:
            seen[state] = index
    return tuple(repeats)


def _find_repeated_points(points: Sequence[Point3]) -> tuple[tuple[int, int, Point3], ...]:
    seen: dict[Point3, int] = {}
    repeats: list[tuple[int, int, Point3]] = []
    final = len(points) - 1
    for index, point in enumerate(points):
        if index == final and point == points[0]:
            continue
        if point in seen:
            repeats.append((seen[point], index, point))
        else:
            seen[point] = index
    return tuple(repeats)


def check_gallery(word: str, repeat: int = 1) -> GalleryCheck:
    """Run all closure and embeddedness checks for one word."""
    parsed = parse_word(word)
    states = gallery_states(parsed, repeat)
    all_points = [state.apply(BASE_CENTRE) for state in states]
    piece_map = evaluate_word(parsed)
    full_map = piece_map.power(repeat)
    closed = full_map == AffineMap.identity()

    repeated_chambers = _find_repeated_states(states)
    repeated_points = _find_repeated_points(all_points)

    polygon: list[Point3]
    if all_points[-1] == all_points[0]:
        polygon = all_points[:-1]
    else:
        polygon = all_points
    intersections = tuple(polygon_intersections(polygon)) if closed else ()

    return GalleryCheck(
        word=parsed,
        repeat=repeat,
        piece_length=len(parsed),
        full_length=len(parsed) * repeat,
        piece_order=piece_map.order(),
        piece_map=piece_map,
        full_map=full_map,
        closed=closed,
        repeated_chambers=repeated_chambers,
        repeated_points=repeated_points,
        intersections=intersections,
        points=tuple(polygon),
    )


def write_check_json(check: GalleryCheck, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(check.to_dict(include_points=True), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def checks_to_json(checks: Iterable[GalleryCheck], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = [check.to_dict(include_points=True) for check in checks]
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
