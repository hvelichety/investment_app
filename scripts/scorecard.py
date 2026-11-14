"""
Weekly scorecard (src/analysis/scorecard.py): appends this week's row per
ticker to data/metrics/history.csv and writes data/metrics/SCORECARD.md.

    python3 scripts/scorecard.py [--issues issues.json]

issues.json: output of `gh issue list --json title,body,createdAt,url`, used
to collect the Saturday gate records into data/metrics/reports.csv.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.analysis.scorecard import update  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues")
    a = parser.parse_args()
    issues = None
    if a.issues and os.path.exists(a.issues):
        issues = json.loads(Path(a.issues).read_text() or "[]")
    print(update(ROOT_DIR, issues))


if __name__ == "__main__":
    main()
