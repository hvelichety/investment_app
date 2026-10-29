# Channel methodology

How the `#stock-*` channels analyze a stock, written down from Pei Ng's
posts (the methodology author) so the agents follow the same method. The
agents read this file on every run; the weekly learning step proposes
changes to the per-ticker playbooks when new posts extend the method.

## 1. Bridge projections with actuals

"When there's data, emotions take less control." Every number is shown
against what was expected:

- Reported results by segment vs consensus projections (actual vs estimate,
  beat or miss in percent). Name the consensus source; flag figures not yet
  checked against the company's filing.
- Projections are refreshed after each report and the projection timeline
  moves forward ("refreshed charts with Q2 final and moved projection timeline").

## 2. Valuation band, not a point target

The core tool. A stock's fair range is

    analyst projection range × historical multiple range

- Profitable companies: consensus average forward EPS for this fiscal year
  and next × a P/E range taken from the stock's own history (RH: 20x to
  30x; NVDA: 30x to 60x), alongside the current P/E on each year's estimate
  (RH chart, Oct 22: $5.36 FY26E and $8.52 FY27E → $107 to $161 and $170
  to $256; current 25.8x and 16.2x). The estimate source is named. The
  channel uses stockanalysis.com (S&P Global data): the Friday review
  records its figures in data/estimates/<TICKER>.yaml with the page's update
  date, and Yahoo Finance fills any year the free page doesn't show.
- Companies valued on revenue (SpaceX): revenue projections × EV / revenue,
  also EV / trailing and EV / run-rate revenue.
- The band is projected to a horizon date (year-end), and the price is
  plotted against it over time, using the price 5 business days after each
  earnings report as the historical marker.

Where the price sits in the band drives position sizing, not a buy/sell call:

- Near the low end: scale in over time ("in full allocation over time"),
  provided projected earnings are not impaired. Time works in favor of the
  low band rising.
- Near the high end: reduce exposure leading up to it ("reducing risk by
  50% with this run-up to 138 from 117; let the remainder run to the 150 to
  160 high range").

## 3. Leading indicators per thesis

Each stock has a few long-term theses and the indicators that move before
the financials do:

- SpaceX: launches and mass to orbit lead Starlink deployment; compute (GW)
  leads AI revenue; segment profit swings.
- Tesla: robotaxi fleet size vs Waymo (registry data, registered vs active),
  FSD use, cost per mile vs Uber.
- RH: margins (tariff impact) as the key KPI.
- NVDA: Data Center share of revenue, platform mix, competitors (AMD, INTC,
  GOOG, AMZN, MSFT).

## 4. Relative performance

Measure the stock against the S&P 500 and Nasdaq since a decision date
(e.g. "RH vs S&P 500: +16.2 pts since Oct 7 close"), so a move is judged
against the market, not in isolation.

## 5. Comparables and sum of parts

Value business segments against market references for similar companies
(SpaceX's AI segment vs OpenAI's private valuation), and track relative
premiums between related stocks (SpaceX vs Tesla market cap for the merger
thesis).

Acquisition reference price (Tesla chart, Oct 26): the gap between the
acquirer's market value and the target's market cap, spread over the
target's diluted shares; reference lines at the target's price plus 25% and
50% of that gap per share, tracked weekly since the acquirer's IPO. Both
share counts are diluted weighted averages from the latest 10-Q, so the two
market values are on the same basis.

## 6. Events

Earnings dates, lockup expiries, product unveilings, regulatory changes.
Each is tied to which thesis or indicator it can move.

## 7. Presentation

Short posts: a bold header, a few bullets with numbers and their
comparison, a chart, then one or two lines of interpretation. Sources are
named, and unverified figures are labeled as such.
