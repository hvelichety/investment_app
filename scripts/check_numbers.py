"""
Number check for a report written outside run_weekly.py.

Usage:
    python3 scripts/check_numbers.py data/factpacks/RH.md draft.md

Prints every figure in the draft that isn't in the fact pack, the same check
the analyst pipeline runs on its memos (src/analysis/agent.py). Each one must
come from a cited news item or be removed. Exit code 1 if any are found.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis.agent import unsupported_numbers  # noqa: E402


def main():
    factpack_path, draft_path = sys.argv[1:3]
    with open(factpack_path, encoding="utf-8") as f:
        factpack = f.read()
    with open(draft_path, encoding="utf-8") as f:
        draft = f.read()
    missing = unsupported_numbers(draft, factpack)
    for figure in missing:
        print(f"not in fact pack: {figure}")
    print(f"{len(missing)} figure(s) not in the fact pack")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
