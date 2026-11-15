"""
Number check shared by the analyst pipeline and the pre-post gate.

Kept free of the Anthropic SDK so the gate and scripts/check_numbers.py run
with only the standard library.
"""

import re
from typing import List

# $14.57B, -$477M, 61.1x, +161.4%, 13,579M, 13.6
NUMBER_RE = re.compile(r"[-+−]?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[BMT%x](?![A-Za-z]))?")
PERIOD_RE = re.compile(r"^(?:19|20)\d{2}(?:Q[1-4])?$")


def unsupported_numbers(memo: str, factpack: str) -> List[str]:
    """Figures in the memo that don't appear verbatim in the fact pack"""
    haystack = factpack.replace("−", "-")
    found = []
    for match in NUMBER_RE.finditer(memo.replace("−", "-")):
        token = match.group(0).lstrip("+")
        bare = token.lstrip("-").lstrip("$")
        # Period labels, list numbering and small counts are not figures
        if PERIOD_RE.match(bare) or re.fullmatch(r"\d", bare):
            continue
        if memo[match.end():match.end() + 1] == "Q":  # "2026Q3"
            continue
        if token not in haystack and token.lstrip("-") not in haystack:
            found.append(token)
    return sorted(set(found))
