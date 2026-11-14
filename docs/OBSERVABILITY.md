# Observability: catching bad output before it posts

Saturday reports post to the #stock channels with no approval step, so the
app checks itself and fixes what it can. A post is held only when the fix
still leaves a problem. Nothing here uses a paid API.

## 1. Pre-post gate (`src/analysis/gate.py`, `scripts/gate.py`)

| Check | When | Automatic fix | Held when |
|---|---|---|---|
| Fact pack is from the latest close (one weekday allowed for a holiday) | Friday build, Saturday 07:23 UTC, Saturday report | Rebuild, up to 3 tries 10 minutes apart on Friday, again Saturday morning; the report run can also start the workflow | Still stale after all retries |
| Market cap = close × shares (within 2%), own and peer | Fact pack build | Line removed from the pack (and any "market cap vs" line using it) | – |
| P/E on the average estimate within 0–200x, band position within -150% to 250% | Fact pack build | That band period removed from the pack | – |
| 1-week move over 25% | Fact pack build | – (warns: confirm with a news item) | – |
| Estimates page last updated over 21 days ago | Fact pack build | – (warns: say so in the post) | – |
| Every figure in the draft is in the pack or an allowed source (news excerpt, Pei's post, last week's pack) | Saturday report | Lines with untraceable figures dropped | Fewer than 2 bullets left |
| No buy/sell call of the app's own | Saturday report | Line dropped | Fewer than 2 bullets left |

`python3 scripts/gate.py draft RH draft.md --allow news.md` writes the fixed
draft, prints the footer for the post (for example "Data checks: 4/4 passed ·
prices as of Nov 13 close · estimates updated Oct 20") and a
`<!-- gate: {...} -->` record for the weekly issue.

## 2. Scorecard (`src/analysis/scorecard.py`, `scripts/scorecard.py`)

The Friday run appends one row per ticker to `data/metrics/history.csv`,
collects the Saturday gate records from the weekly issues into
`data/metrics/reports.csv`, and writes `data/metrics/SCORECARD.md`.

| Divergence | Flag when |
|---|---|
| stockanalysis.com vs Yahoo, same fiscal year | Over 5% apart |
| Our estimate vs Pei's latest (`data/pei/<TICKER>.yaml`, last 45 days) | Over 2% apart, or a different band zone |
| Week to week | Share count moves over 2%, consensus over 5%, or the band zone changes on a price move under 3% |
| Band calls vs what happened | Track record: below / near-low calls should beat the S&P 500 over 4 and 12 weeks, above / near-high calls should lag it |
