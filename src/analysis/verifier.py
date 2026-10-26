"""
Verifier agent: checks every factual claim in a report before it is shared.

Figures that cite the fact pack are checked against it (value, period,
segment, source); anything else (news, events, outside figures) has to be
found in a primary source or reputable outlet via web search / fetch. The
model records findings through a strict tool, and code then downgrades any
finding whose evidence URL never came back from a search or fetch, so a
made-up citation can't count as verified.
"""

from dataclasses import dataclass, field
from typing import List

from .agent import WEB_FETCH, WEB_SEARCH, run_tool_loop

VERIFIER_SYSTEM = """You are an independent fact-checker for an investment research team. Nothing leaves the team until you have checked it.

Go through the report and check every factual claim: each number, date, event, quote and attribution. Skip clearly labeled opinion, but flag judgment presented as fact.

How to check:
- A figure that cites a fact pack source key: compare it with the fact pack, including period, segment, units and source. The fact pack has already been checked against the company's filings, so a match is verified with basis "fact_pack".
- Anything else: find it yourself with web search and web fetch. Prefer primary sources (company releases and IR pages, SEC filings, regulators, official registries). Otherwise use at least one established outlet, and say which. Search results are evidence only if they state the claim; a headline that hints at it is not enough.
- Third-party estimates (‡) are verified only as "this outlet published this estimate", never as company data.

Statuses:
- verified: the fact pack or a source you read states it, with the same number and period.
- contradicted: a reliable source states something different. Give the correct figure in the note.
- unverified: you could not confirm it either way. Explain what you looked for.

Quote the evidence briefly, word for word where you can. Use only URLs that your searches or fetches returned.
When you have checked everything, call record_findings once with all findings, then stop."""

STATUSES = ["verified", "contradicted", "unverified"]
BASES = ["fact_pack", "primary_source", "secondary_source", "none"]

RECORD_FINDINGS = {
    "name": "record_findings",
    "description": "Record the result of checking every factual claim in the report. Call once, at the end.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string", "description": "The claim as written in the report"},
                        "status": {"type": "string", "enum": STATUSES},
                        "basis": {"type": "string", "enum": BASES},
                        "source_url": {"type": "string", "description": "URL of the evidence, or empty for fact_pack / none"},
                        "evidence": {"type": "string", "description": "Short quote or figure from the source"},
                        "note": {"type": "string", "description": "Correct figure if contradicted, what was searched if unverified"},
                    },
                    "required": ["claim", "status", "basis", "source_url", "evidence", "note"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["findings"],
        "additionalProperties": False,
    },
}


@dataclass
class Verification:
    findings: List[dict] = field(default_factory=list)

    def by_status(self, status: str) -> List[dict]:
        return [f for f in self.findings if f["status"] == status]

    @property
    def problems(self) -> List[dict]:
        return [f for f in self.findings if f["status"] != "verified"]

    @property
    def clean(self) -> bool:
        return bool(self.findings) and not self.problems


def _check_urls(findings: List[dict], seen_urls: set, known_urls: set) -> List[dict]:
    """A web-based finding counts only if its URL was really returned or is a fact pack source"""
    checked = []
    for f in findings:
        f = dict(f)
        web = f["basis"] in ("primary_source", "secondary_source")
        if f["status"] == "verified" and web and f["source_url"] not in seen_urls | known_urls:
            f["status"] = "unverified"
            f["note"] = (f"Evidence URL was not returned by any search or fetch, so the citation "
                         f"couldn't be confirmed. {f['note']}").strip()
        checked.append(f)
    return checked


def verify_report(report: str, factpack: str, client, known_urls=(), extra_figures=()) -> Verification:
    """Check a report's claims; extra_figures are numbers the code check couldn't find in the fact pack"""
    hint = ""
    if extra_figures:
        hint = ("\n\nThese figures are not in the fact pack, so each needs an outside source or should be "
                "marked unverified: " + ", ".join(extra_figures))
    prompt = (f"<fact_pack>\n{factpack}\n</fact_pack>\n\n<report>\n{report}\n</report>{hint}\n\n"
              "Check every factual claim in the report.")

    recorded = []

    def on_tool(name, tool_input):
        if name == "record_findings":
            recorded.extend(tool_input["findings"])
            return f"Recorded {len(tool_input['findings'])} findings."
        return f"Unknown tool {name}"

    tools = [dict(WEB_SEARCH, max_uses=15), dict(WEB_FETCH, max_uses=10), RECORD_FINDINGS]
    run = run_tool_loop(client, VERIFIER_SYSTEM, prompt, tools, on_tool=on_tool)
    if not recorded:
        raise RuntimeError("Verifier finished without recording findings")
    return Verification(_check_urls(recorded, run.seen_urls, set(known_urls)))
