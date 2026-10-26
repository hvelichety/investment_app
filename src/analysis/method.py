"""
Method review: learn from the methodology author's new posts.

Each week the author's posts in a ticker's channel (text and charts) are
compared with docs/METHODOLOGY.md and the ticker's playbook. When the posts
show a deliberate change in method (a new KPI tracked, a new multiple
range, a new decision date, a new comparable), the agent returns a revised
playbook; the weekly workflow opens it as a pull request, so a person
approves every change before the agents use it. The figures in the posts
are also listed so the verifier can fact-check them.
"""

import base64
import json
from dataclasses import dataclass, field
from typing import List

import yaml

from .agent import FALLBACK_BETA, MODEL, _text

METHOD_SYSTEM = """You keep a research channel's analysis method up to date. The methodology author posts analysis in the stock channels, and agents reproduce that method from a methodology document and a playbook per ticker.

You get the methodology, one ticker's playbook, and the author's posts from the past week (text and charts). Decide whether the posts change the method for this ticker:
- a metric, KPI or leading indicator the author has started tracking
- a valuation band change: multiple range, estimate basis, horizon date
- a new decision date to measure relative performance from
- a new thesis, comparable, peer or event to watch
- a new data source, or a different way of presenting results
Count only deliberate method: a number tracked over time, a range set, a chart built, a rule stated. Passing remarks, opinions on news, and one-off reactions don't change the method. Read the charts: axis labels, legends and annotations often state the method more precisely than the text.

If the method changed, return the complete revised playbook YAML. Keep every existing key and comment, change only what the posts support, and add a short comment on each changed line citing the post date. If nothing changed, return the playbook exactly as given and set changed to false.

Also list every factual claim in the posts (figures, counts, dates, attributions) as short standalone sentences, so they can be fact-checked."""

METHOD_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "What the author posted this week, in two or three sentences"},
        "changed": {"type": "boolean"},
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "what": {"type": "string"},
                    "why": {"type": "string"},
                    "quote": {"type": "string", "description": "The post text or chart detail it rests on"},
                    "post_date": {"type": "string"},
                },
                "required": ["what", "why", "quote", "post_date"],
                "additionalProperties": False,
            },
        },
        "playbook_yaml": {"type": "string"},
        "claims": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "changed", "changes", "playbook_yaml", "claims"],
    "additionalProperties": False,
}


@dataclass
class MethodReview:
    summary: str
    changed: bool
    changes: List[dict] = field(default_factory=list)
    playbook_yaml: str = ""
    claims: List[str] = field(default_factory=list)
    rejected: str = ""   # why a proposed playbook was not accepted


def _validate(original: dict, revised_yaml: str) -> str:
    """Empty string if the revised playbook is acceptable, else the reason"""
    try:
        revised = yaml.safe_load(revised_yaml)
    except yaml.YAMLError as e:
        return f"revised playbook is not valid YAML: {e}"
    if not isinstance(revised, dict):
        return "revised playbook is not a mapping"
    if revised.get("ticker") != original.get("ticker"):
        return "revised playbook changes the ticker"
    dropped = set(original) - set(revised)
    if dropped:
        return f"revised playbook drops keys: {', '.join(sorted(dropped))}"
    return ""


def review_method(posts, playbook_text: str, methodology: str, client) -> MethodReview:
    playbook = yaml.safe_load(playbook_text)
    content = []
    for post in posts:
        for media_type, data in post.images:
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": media_type, "data": base64.standard_b64encode(data).decode()}})
            content.append({"type": "text", "text": f"(chart above: posted {post.date})"})
    posts_text = "\n\n".join(f"[{p.date}] {p.text}" for p in posts)
    content.append({"type": "text", "text": (
        f"<methodology>\n{methodology}\n</methodology>\n\n"
        f"<playbook>\n{playbook_text}\n</playbook>\n\n"
        f"<posts>\n{posts_text}\n</posts>\n\n"
        "Review this week's posts against the method."
    )})

    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": METHOD_SCHEMA}},
        system=METHOD_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    result = json.loads(_text(response))
    review = MethodReview(result["summary"], result["changed"], result["changes"],
                          result["playbook_yaml"], result["claims"])
    if review.changed:
        review.rejected = _validate(playbook, review.playbook_yaml)
        if review.rejected:
            review.changed = False
    return review
