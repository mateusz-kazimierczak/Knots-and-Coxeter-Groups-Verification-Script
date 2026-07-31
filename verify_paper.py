"""One-command check of the manuscript's explicit gallery words."""

from coxeter_knot_checker.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["verify", "--output", "results"]))
