# Pei's stated figures

The Friday method review records here any estimate, band edge or band zone
that Pei states in a post, one file per ticker (`<TICKER>.yaml`). The weekly
scorecard (`scripts/scorecard.py`) compares ours with his latest entry from the
past 45 days and flags an estimate gap over 2% or a different band zone.

```yaml
ticker: RH
entries:
  - date: 2026-11-10           # date of the post
    post: https://...slack.com/archives/C0A22TTJSN5/p...   # permalink
    period: 0y                 # yfinance period, as in data/estimates/
    estimate_avg: 5.36         # the EPS (or revenue, $M) his band uses
    band_low: 107.20           # optional
    band_high: 160.80          # optional
    zone: mid band             # optional: below the band | near the low end | mid band | near the high end | above the band
```

Record only figures he actually wrote or charted; leave a field out rather
than estimating it.
