"""
Commentary agent: turns the week's numbers and news into a channel update.

Reads the fact pack (with this week's market section), the analyst memo and
the playbook, searches for the week's company news, and returns a short
Slack draft in the channel's style plus a thesis scorecard. Output comes
back through a strict tool so each part can be checked separately; news
items whose URL never came back from a search are dropped.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import yaml

from .agent import WEB_FETCH, WEB_SEARCH, run_tool_loop

COMMENTARY_SYSTEM = """You write the weekly update for a small investment channel. Readers already follow the company and hold positions; they want what changed and what it means for the thesis, fast.

Write in the channel's style:
- a bold one-line header with the company and the week
- 3 to 6 bullets, each one fact with its number and its comparison (actual vs estimate, this week vs last, us vs peer)
- one or two lines on what it means for the thesis, labeled as view, not fact
- the next catalyst and its date when known
Plain and specific. No hype, no price targets of your own, no buy or sell calls. When the fact pack has a valuation band, report where the price sits in it and what the channel's method does in that zone (scale in near the low end, reduce exposure near the high end), labeled as the channel's method. Slack formatting: *bold*, • bullets, no Markdown headings.

Follow the channel methodology you are given; it is how this channel analyzes every stock.

Numbers:
- Use figures from the fact pack exactly as written (same rounding and units) and keep † and ‡ markers.
- A figure from this week's news may be used only if it is in a news item you list, and the bullet must name the outlet.
- Never compute new numbers or use figures from memory.

News: search for company news from the past 7 days (and peers named in the playbook when relevant to the thesis). Prefer company releases, SEC filings and regulators, then established outlets. Leave out rumors unless they move the thesis, and then call them rumors. List every news item you rely on with its URL as returned by search.

Scorecard: for each thesis question in the playbook, say whether this week's data strengthens or weakens it, or brings nothing new, with one line of evidence.

When done, call submit_commentary once."""

DIRECTIONS = ["strengthens", "weakens", "no_change", "no_new_data"]

SUBMIT_COMMENTARY = {
    "name": "submit_commentary",
    "description": "Submit the weekly commentary. Call once, at the end.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "slack_post": {"type": "string", "description": "The channel update, Slack formatting"},
            "scorecard": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "direction": {"type": "string", "enum": DIRECTIONS},
                        "evidence": {"type": "string"},
                    },
                    "required": ["question", "direction", "evidence"],
                    "additionalProperties": False,
                },
            },
            "watch_next": {"type": "array", "items": {"type": "string"}},
            "news": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "headline": {"type": "string"},
                        "outlet": {"type": "string"},
                        "date": {"type": "string", "description": "YYYY-MM-DD"},
                        "url": {"type": "string"},
                    },
                    "required": ["headline", "outlet", "date", "url"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["slack_post", "scorecard", "watch_next", "news"],
        "additionalProperties": False,
    },
}


@dataclass
class Commentary:
    slack_post: str
    scorecard: List[dict]
    watch_next: List[str]
    news: List[dict]
    dropped_news: List[dict] = field(default_factory=list)

    def text(self) -> str:
        """Everything a reader would see, for the number check and the verifier"""
        lines = [self.slack_post, "", "Thesis scorecard:"]
        lines += [f"- {s['question']} → {s['direction']}: {s['evidence']}" for s in self.scorecard]
        lines += ["", "Watch next:"] + [f"- {w}" for w in self.watch_next]
        lines += ["", "News used:"] + [f"- {n['outlet']}, {n['date']}: {n['headline']} ({n['url']})" for n in self.news]
        return "\n".join(lines)


def write_commentary(factpack: str, memo: str, playbook: dict, week_ending: str, client,
                     feedback: Optional[List[str]] = None, previous: Optional["Commentary"] = None,
                     methodology: str = "") -> Commentary:
    prompt = (
        f"Week ending {week_ending}. Cover the 7 days up to that date.\n\n"
        + (f"<methodology>\n{methodology}\n</methodology>\n\n" if methodology else "")
        + f"<playbook>\n{yaml.safe_dump(playbook, sort_keys=False)}</playbook>\n\n"
        f"<fact_pack>\n{factpack}\n</fact_pack>\n\n"
        + (f"<analyst_memo>\n{memo}\n</analyst_memo>\n\n" if memo else "")
    )
    if feedback and previous:
        prompt += (
            f"<previous_draft>\n{previous.text()}\n</previous_draft>\n\n"
            "<fact_check>\nThe fact-checker could not stand behind these claims:\n- " + "\n- ".join(feedback)
            + "\n</fact_check>\n\nRewrite the commentary. Correct contradicted claims with the checker's figure "
            "only if it gives a source; otherwise remove them. Remove unverified claims or say plainly that "
            "they are unconfirmed. Keep everything else."
        )
    else:
        prompt += "Write this week's commentary."

    submitted = {}

    def on_tool(name, tool_input):
        if name == "submit_commentary":
            submitted.update(tool_input)
            return "Submitted."
        return f"Unknown tool {name}"

    tools = [dict(WEB_SEARCH, max_uses=10), dict(WEB_FETCH, max_uses=5), SUBMIT_COMMENTARY]
    run = run_tool_loop(client, COMMENTARY_SYSTEM, prompt, tools, on_tool=on_tool)
    if not submitted:
        raise RuntimeError("Commentary agent finished without submitting")

    # A revision may keep news found (and URL-checked) in the previous draft
    allowed = run.seen_urls | {n["url"] for n in (previous.news if previous else [])}
    kept, dropped = [], []
    for item in submitted["news"]:
        (kept if item["url"] in allowed else dropped).append(item)
    return Commentary(submitted["slack_post"], submitted["scorecard"], submitted["watch_next"], kept, dropped)
