"""Command-line entry point for the verification package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import check_gallery, parse_word
from .paper_words import (
    THEOREM_3_LENGTH_40,
    THEOREM_3_SYMMETRIC_PIECE,
    THEOREM_5_STATED_LENGTHS,
    THEOREM_5_WORDS,
)
from .theorem3 import run_search


def verify_paper_examples(output_dir: str | Path | None = None) -> dict[str, object]:
    """Check the explicit gallery words, without attempting knot identification."""
    examples: list[tuple[str, str, int, int | None]] = [
        (
            "Theorem 3 symmetric piece",
            THEOREM_3_SYMMETRIC_PIECE,
            3,
            len(parse_word(THEOREM_3_SYMMETRIC_PIECE)),
        ),
        (
            "Theorem 3 length-40 gallery",
            THEOREM_3_LENGTH_40,
            1,
            40,
        ),
    ]
    for name, word in THEOREM_5_WORDS.items():
        examples.append(
            (
                f"Theorem 5 word labelled {name}",
                word,
                3,
                THEOREM_5_STATED_LENGTHS[name],
            )
        )

    records: list[dict[str, object]] = []
    passed = True
    for label, word, repeat, expected_piece_length in examples:
        check = check_gallery(word, repeat=repeat)
        length_matches = (
            expected_piece_length is None
            or check.piece_length == expected_piece_length
        )
        expected_order = 3 if repeat == 3 else 1
        order_matches = check.piece_order == expected_order
        record = {
            "label": label,
            "expected_piece_length": expected_piece_length,
            "length_matches": length_matches,
            "expected_piece_order": expected_order,
            "order_matches": order_matches,
            **check.to_dict(include_points=True),
        }
        record_passed = length_matches and order_matches and check.valid_knot
        record["passed"] = record_passed
        passed = passed and record_passed
        records.append(record)

    result: dict[str, object] = {
        "scope": (
            "Checks only word length, group order, closure, repeated chambers/points, "
            "and non-adjacent segment intersections. It does not identify knot type."
        ),
        "passed": passed,
        "examples": records,
    }

    if output_dir is not None:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / "gallery_checks.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        lines = [
            "# Gallery validity checks",
            "",
            "These checks establish only that each listed word traces a closed, embedded polygonal curve.",
            "They do not identify the knot type.",
            "",
            "| Example | Piece length | Repeat | Piece order | Closed | Repeated chambers | Intersections | Valid knot |",
            "|---|---:|---:|---:|:---:|---:|---:|:---:|",
        ]
        for record in records:
            lines.append(
                "| {label} | {piece_length} | {repeat} | {piece_order} | {closed} | "
                "{repeated} | {intersections} | {valid} |".format(
                    label=record["label"],
                    piece_length=record["piece_length"],
                    repeat=record["repeat"],
                    piece_order=record["piece_order"],
                    closed="yes" if record["closed"] else "no",
                    repeated=len(record["repeated_chambers"]),
                    intersections=len(record["segment_intersections"]),
                    valid="yes" if record["valid_knot"] else "no",
                )
            )
        (output / "gallery_checks.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    return result


def _print_verification(result: dict[str, object]) -> None:
    records = result["examples"]
    assert isinstance(records, list)
    print(
        f"{'example':42} {'piece':>7} {'repeat':>6} {'order':>6} "
        f"{'closed':>7} {'repeats':>8} {'hits':>5} {'valid':>7}"
    )
    print("-" * 96)
    for record in records:
        assert isinstance(record, dict)
        print(
            f"{str(record['label'])[:42]:42} "
            f"{int(record['piece_length']):7d} "
            f"{int(record['repeat']):6d} "
            f"{str(record['piece_order']):>6} "
            f"{str(bool(record['closed'])):>7} "
            f"{len(record['repeated_chambers']):8d} "
            f"{len(record['segment_intersections']):5d} "
            f"{str(bool(record['valid_knot'])):>7}"
        )
    print(f"\noverall: {'PASS' if result['passed'] else 'FAIL'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m coxeter_knot_checker",
        description="Exact closure and embeddedness checks for the manuscript galleries.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser(
        "verify", help="check the explicit Theorem 3 and Theorem 5 words"
    )
    verify.add_argument("--output", type=Path, default=None)

    check = subparsers.add_parser("check", help="check one A/B/C/D word")
    check.add_argument("word")
    check.add_argument("--repeat", type=int, default=1)
    check.add_argument("--json", action="store_true")

    search = subparsers.add_parser(
        "search", help="run Theorem 3 pruning and simplification"
    )
    search.add_argument("--max-length", type=int, default=14)
    search.add_argument("--workers", type=int, default=None)
    search.add_argument("--output", type=Path, default=Path("results/theorem3"))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "verify":
        result = verify_paper_examples(args.output)
        _print_verification(result)
        return 0 if result["passed"] else 1

    if args.command == "check":
        result = check_gallery(args.word, repeat=args.repeat)
        if args.json:
            print(json.dumps(result.to_dict(include_points=True), indent=2, sort_keys=True))
        else:
            print(f"piece length: {result.piece_length}")
            print(f"full length:  {result.full_length}")
            print(f"piece order: {result.piece_order}")
            print(f"closed:      {result.closed}")
            print(f"repeated chambers: {len(result.repeated_chambers)}")
            print(f"segment intersections: {len(result.intersections)}")
            print(f"valid knot: {result.valid_knot}")
        return 0 if result.valid_knot else 1

    if args.command == "search":
        report = run_search(
            max_length=args.max_length,
            output_dir=args.output,
            workers=args.workers,
        )
        print(
            f"{'length':>6} {'raw':>10} {'unique':>10} "
            f"{'simplified':>12} {'visual':>8}"
        )
        print("-" * 54)
        for row in report["lengths"]:
            assert isinstance(row, dict)
            print(
                f"{int(row['piece_length']):6d} "
                f"{int(row['raw_candidates']):10d} "
                f"{int(row['unique_candidates']):10d} "
                f"{int(row['simplified_to_triangle']):12d} "
                f"{int(row['remaining_for_visual_inspection']):8d}"
            )
        print(f"\nresults written to {args.output}")
        return 0

    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    sys.exit(main())
