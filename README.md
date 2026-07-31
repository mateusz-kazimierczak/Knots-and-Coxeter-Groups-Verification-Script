# Coxeter Knot Checker

This is a verification package for the manuscript **“Knots and Coxeter Groups.”** Its scope is limited to two tasks:

1. check that a word in `A, B, C, D` traces a **closed, non-self-intersecting polygonal curve** in the affine `B~3` tessellation; and
2. reproduce the **enumeration, pruning, and elementary simplification** stage of the exhaustive search used for Theorem 3, leaving the final cases for visual inspection.

The package does **not** compute knot invariants and does **not** try to identify a curve as `3_1`, `9_35`, `9_40`, `9_41`, or `9_47`. For Theorem 5 it checks only that the four printed words are valid polygonal knots in the sense used in the paper: closed and without self-intersection.

There are no third-party runtime dependencies.

## Layout

```text
src/coxeter_knot_checker/
    core.py          exact word, closure, and embeddedness checks
    theorem3.py      exhaustive search and simplification extension
    paper_words.py   words copied from Theorems 3 and 5
    __main__.py      command-line interface

verify_paper.py      one-command check of the explicit manuscript words
search_theorem3.py   one-command Theorem 3 search
results/             generated reports from the verified run
```

The mathematical code is therefore concentrated in one core module and one search extension.

## Exact model

The base chamber has vertices

```text
A = (0, 0, 0)
B = (2, 0, 0)
C = (1, 1, 0)
D = (1, 1, 1)
```

Its centre is `(1, 1/2, 1/4)`. The program multiplies all chamber-centre coordinates by four, so the initial centre is `(4, 2, 1)` and every computation uses integers.

The four face reflections are implemented exactly as

```text
A: (x, y, z) -> (8-y, 8-x, z)   # on scaled centres
B: (x, y, z) -> (y, x, z)
C: (x, y, z) -> (x, z, y)
D: (x, y, z) -> (x, y, -z)
```

For a word `w`, the program builds the chamber-centre path of `w`, or of `w^3` when the piece is repeated three times.

## What “valid knot” means here

`check_gallery(word, repeat)` reports `valid_knot = true` exactly when:

- the final affine transformation is the identity, so the gallery closes;
- no chamber or centre is visited twice, except for the final return to the initial chamber; and
- no two non-adjacent centreline segments intersect, touch, or overlap.

The segment tests use exact rational arithmetic. No floating-point tolerance is used.

## Run the manuscript checks

Install the supplied wheel:

```bash
python -m pip install coxeter_knot_checker-0.1.0-py3-none-any.whl
coxeter-knot-checker verify --output results
```

From an unpacked source archive, the same check can be run without installing anything beyond Python:

```bash
PYTHONPATH=src python verify_paper.py
```

After installation:

```bash
coxeter-knot-checker verify --output results
```

The generated files are:

```text
results/gallery_checks.md
results/gallery_checks.json
```

The checked run gives:

| Example | Piece length | Repeat | Piece order | Closed | Repeated chambers | Segment intersections | Valid polygonal knot |
|---|---:|---:|---:|:---:|---:|---:|:---:|
| Theorem 3 symmetric piece | 14 | 3 | 3 | yes | 0 | 0 | yes |
| Theorem 3 length-40 gallery | 40 | 1 | 1 | yes | 0 | 0 | yes |
| Theorem 5 word labelled `9_35` | 174 | 3 | 3 | yes | 0 | 0 | yes |
| Theorem 5 word labelled `9_40` | 116 | 3 | 3 | yes | 0 | 0 | yes |
| Theorem 5 word labelled `9_41` | 186 | 3 | 3 | yes | 0 | 0 | yes |
| Theorem 5 word labelled `9_47` | 250 | 3 | 3 | yes | 0 | 0 | yes |

This table makes no claim about the specific knot type of the four Theorem 5 curves.

## Check one word

```bash
coxeter-knot-checker check CBDCDCDCBADCBA --repeat 3
```

For a machine-readable result, add `--json`.

## Run the Theorem 3 search

```bash
python search_theorem3.py
```

or:

```bash
coxeter-knot-checker search \
    --max-length 14 \
    --workers 8 \
    --output results/theorem3
```

The search uses only the following reductions:

1. adjacent equal letters are omitted because they immediately cross a face and cross back;
2. a partial word is stopped as soon as it revisits a chamber centre;
3. completed pieces with an odd number of `D` letters are omitted, as in the paper;
4. the piece must have exact group order three;
5. the full word `w^3` must be a closed embedded polygon;
6. cyclic shifts and reversal are grouped because they select a different starting point or traversal direction on the same closed polygon; and
7. three consecutive vertices `a,b,c` are replaced by the single edge `a-c` when the triangle `abc` is disjoint from every other polygon edge. This elementary operation is repeated until no further vertex can be removed.

A curve that reduces to three vertices is set aside as an obvious trivial case. Every remaining curve is exported, without knot-type classification, for visual inspection.

The verified run gives:

| Piece length | Raw candidates | Unique candidates | Simplified to a triangle | Left for visual inspection |
|---:|---:|---:|---:|---:|
| 2 | 4 | 2 | 2 | 0 |
| 4 | 20 | 5 | 5 | 0 |
| 6 | 156 | 20 | 20 | 0 |
| 8 | 536 | 43 | 43 | 0 |
| 10 | 3,340 | 198 | 198 | 0 |
| 12 | 19,860 | 895 | 895 | 0 |
| 14 | 156,576 | 5,780 | 5,762 | 18 |

Odd lengths from 1 through 13 produce no candidates.

The output directory contains one CSV file per length, a count summary, and the final 18 cases:

```text
results/theorem3/summary.json
results/theorem3/length_14_candidates.csv
results/theorem3/remaining_for_visual_inspection.txt
results/theorem3/remaining_for_visual_inspection.json
```

The text file contains words that can be pasted into the existing interactive visualizer. The JSON file also contains the exact full and simplified centre coordinates, scaled by four.

## Tests

```bash
python -m unittest discover -s tests -v
```

The routine suite checks the exact reflections, Coxeter relations, segment-intersection predicate, Theorem 3 witnesses, and all four Theorem 5 words. The complete search regression is intentionally optional because it is slower:

```bash
RUN_FULL_SEARCH=1 python -m unittest tests.test_theorem3.Theorem3SearchTests.test_full_length_14_regression -v
```

On the verification machine, the complete search through length 14 took about 30 seconds with eight worker processes.
