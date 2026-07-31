# Verification run

The package was run against the words printed in Theorems 3 and 5 of the supplied manuscript.

## Core gallery checks

All six checked examples passed the exact closure and embeddedness tests:

| Example | Piece length | Repeat | Piece order | Closed | Repeated chambers | Non-adjacent intersections | Valid polygonal knot |
|---|---:|---:|---:|:---:|---:|---:|:---:|
| Theorem 3 symmetric piece | 14 | 3 | 3 | yes | 0 | 0 | yes |
| Theorem 3 length-40 gallery | 40 | 1 | 1 | yes | 0 | 0 | yes |
| Theorem 5 word labelled `9_35` | 174 | 3 | 3 | yes | 0 | 0 | yes |
| Theorem 5 word labelled `9_40` | 116 | 3 | 3 | yes | 0 | 0 | yes |
| Theorem 5 word labelled `9_41` | 186 | 3 | 3 | yes | 0 | 0 | yes |
| Theorem 5 word labelled `9_47` | 250 | 3 | 3 | yes | 0 | 0 | yes |

This verifies only that the four Theorem 5 words define closed embedded polygonal curves. It does not verify their specific knot types.

## Theorem 3 search stage

The exhaustive pruning and simplification run through piece length 14 produced:

| Piece length | Raw candidates | Unique candidates | Simplified to a triangle | Left for visual inspection |
|---:|---:|---:|---:|---:|
| 2 | 4 | 2 | 2 | 0 |
| 4 | 20 | 5 | 5 | 0 |
| 6 | 156 | 20 | 20 | 0 |
| 8 | 536 | 43 | 43 | 0 |
| 10 | 3,340 | 198 | 198 | 0 |
| 12 | 19,860 | 895 | 895 | 0 |
| 14 | 156,576 | 5,780 | 5,762 | 18 |

Odd lengths from 1 to 13 produced no candidates. The package intentionally stops with the 18 length-14 cases and exports them for visual inspection.

## Commands used

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src RUN_FULL_SEARCH=1 python -m unittest discover -s tests -v
PYTHONPATH=src python -m coxeter_knot_checker verify --output results
PYTHONPATH=src python -m coxeter_knot_checker search --max-length 14 --workers 8 --output results/theorem3
```

The routine suite passed 7 tests with one optional full-search test skipped. The full suite, including the complete length-14 regression, passed all 8 tests. The complete search took approximately 30 seconds on the verification machine with eight worker processes.
