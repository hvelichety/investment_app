"""
Analyst agent: writes a memo from the fact pack, then a CFO-style review.

Pipeline (every step is plain code except the two model calls):
  1. Analyst (Claude) writes the memo from the fact pack and ticker playbook.
  2. Number check (code): every figure in the memo must appear verbatim in
     the fact pack. Anything else is an unsupported number.
  3. CFO reviewer (Claude) checks claims and reasoning against the fact pack
     and returns structured issues.
  4. If either check finds problems, the analyst revises once with the
     issues attached, and both checks run again on the revision.
The result is a draft for human review, never posted automatically.
"""

import json
import re
from dataclasses import dataclass, field
from typing import List

import anthropic
import yaml

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

ANALYST_SYSTEM = """You are a senior equity analyst writing for experienced investors and a CFO.

You will receive a fact pack and a playbook for one company. The fact pack is the only source of numbers you may use.

Rules:
- Copy every figure exactly as it is written in the fact pack (same rounding and units, e.g. "$14.57B", "61.1x", "+161.4%"). Do not compute new numbers, round differently, or bring in figures from memory. If a number you want is not in the fact pack, describe the point without a number or say the data is missing.
- After each figure, cite its source key in brackets, e.g. "$14.57B [q3_2026_release]". Keep the † and ‡ markers when you quote derived or third-party figures, and say plainly that ‡ figures are third-party estimates.
- Separate what the company reported, what is calculated from it, and your judgment.
- No price targets and no buy or sell recommendation.

Structure the memo in Markdown:
1. Headline (one sentence: what changed this quarter)
2. What changed (by segment)
3. Leading indicators
4. Valuation
5. Bull case
6. Bear case
7. Risks and open questions (including what the data cannot answer)

Answer the playbook's thesis questions within those sections. Be concise and specific; no filler."""

REVIEWER_SYSTEM = """You are the CFO reviewing an analyst memo before it goes to investors.

Check the memo strictly against the fact pack. Flag:
- any number not in the fact pack, or attached to the wrong period, segment or source
- claims the fact pack does not support, or that overstate it (e.g. treating a one-quarter swing as a trend)
- third-party estimates (‡) or derived figures (†) presented as reported company data
- missing material context: a key negative in the fact pack the memo ignores
- price targets or buy/sell calls

Do not flag style preferences. Return pass only if there is nothing material to fix."""

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "revise"]},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string", "description": "The memo text at issue"},
                    "problem": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["quote", "problem", "fix"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "issues"],
    "additionalProperties": False,
}

# $14.57B, -$477M, 61.1x, +161.4%, 13,579M, 13.6
NUMBER_RE = re.compile(r"[-+−]?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[BMT%x](?![A-Za-z]))?")
PERIOD_RE = re.compile(r"^(?:19|20)\d{2}(?:Q[1-4])?$")


@dataclass
class MemoResult:
    memo: str
    unsupported_numbers: List[str]
    review: dict
    revised: bool
    history: List[dict] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.unsupported_numbers and self.review.get("verdict") == "pass"


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


def _text(message) -> str:
    if message.stop_reason == "refusal":
        raise RuntimeError(f"Model declined the request: {message.stop_details}")
    return "".join(b.text for b in message.content if b.type == "text").strip()


def _write_memo(client, user_content: str) -> str:
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": "high"},
        system=ANALYST_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        return _text(stream.get_final_message())


def _review(client, factpack: str, memo: str) -> dict:
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
        system=REVIEWER_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"<fact_pack>\n{factpack}\n</fact_pack>\n\n<memo>\n{memo}\n</memo>",
        }],
    )
    return json.loads(_text(response))


def run_analyst(factpack: str, playbook: dict, client: anthropic.Anthropic = None) -> MemoResult:
    client = client or anthropic.Anthropic()
    brief = (
        f"<playbook>\n{yaml.safe_dump(playbook, sort_keys=False)}</playbook>\n\n"
        f"<fact_pack>\n{factpack}\n</fact_pack>\n\n"
        "Write the memo."
    )

    memo = _write_memo(client, brief)
    numbers = unsupported_numbers(memo, factpack)
    review = _review(client, factpack, memo)
    history = [{"memo": memo, "unsupported_numbers": numbers, "review": review}]

    if not numbers and review["verdict"] == "pass":
        return MemoResult(memo, numbers, review, revised=False, history=history)

    feedback = []
    if numbers:
        feedback.append("These figures are not in the fact pack; remove them or replace them "
                        "with the fact pack's exact figure: " + ", ".join(numbers))
    for issue in review["issues"]:
        feedback.append(f'"{issue["quote"]}": {issue["problem"]} Fix: {issue["fix"]}')
    revision_brief = (
        f"{brief}\n\n<previous_draft>\n{memo}\n</previous_draft>\n\n"
        "<reviewer_feedback>\n- " + "\n- ".join(feedback) + "\n</reviewer_feedback>\n\n"
        "Rewrite the memo, fixing every point of feedback."
    )

    memo = _write_memo(client, revision_brief)
    numbers = unsupported_numbers(memo, factpack)
    review = _review(client, factpack, memo)
    history.append({"memo": memo, "unsupported_numbers": numbers, "review": review})
    return MemoResult(memo, numbers, review, revised=True, history=history)
