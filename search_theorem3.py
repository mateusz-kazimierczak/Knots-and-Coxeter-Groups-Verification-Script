"""Run the exhaustive pruning/simplification stage for Theorem 3."""

from coxeter_knot_checker.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["search", "--max-length", "14", "--output", "results/theorem3"]))
