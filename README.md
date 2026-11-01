# Market Calendar API (v0.1)

Trading-relevant calendars for AI agents, paid per call via x402 (USDC on Base).

| Endpoint | Returns | Price |
|---|---|---|
| `/v1/briefing?days=7` | **Trading briefing:** all scheduled market events of the next 1-31 days in one call (releases, Fed/ECB, expirations, rebalancing, auctions, banking holidays) | 0.0455 USDC |
| `/v1/opex?date=` | Is the date a US monthly / triple witching / weekly / VIX / Eurex expiration; next ones | 0.0205 USDC |
| `/v1/opex-calendar?year=&venue=` | All monthly expirations of a year (US, VIX, Eurex), holiday-adjusted | 0.0205 USDC |
| `/v1/vix-expiry?count=` | Next VIX futures/options expirations | 0.0205 USDC |
| `/v1/next-release?indicator=CPI` | Next CPI / NFP / PPI / GDP / PCE release with time (ET, UTC) | 0.0225 USDC |
| `/v1/releases?from=&to=` | US economic releases in a date range | 0.0225 USDC |
| `/v1/next-meeting?bank=fed` | Next Fed (FOMC) / ECB decision with statement and press conference times | 0.0245 USDC |
| `/v1/meetings?bank=&year=` | All Fed/ECB meetings of a year | 0.0245 USDC |
| `/v1/auctions?from=&to=&term=` | US Treasury auctions: upcoming and results | 0.0265 USDC |
| `/v1/next-auction?term=` | Next announced Treasury auction | 0.0265 USDC |
| `/v1/is-banking-day?zone=TARGET2` | Banking/settlement day for TARGET2, US (Fedwire) or CH | 0.0285 USDC |
| `/v1/banking-holidays?zone=&year=` | Banking holidays of a year | 0.0285 USDC |
| `/v1/rebalance?index=&year=` | S&P 500, Nasdaq-100, Russell (semi-annual), DAX rebalancing dates | 0.0405 USDC |
| `/v1/public-holidays?country=CH&subdiv=ZH&year=` | Statutory public holidays of 150+ countries and their regions | 0.0305 USDC |
| `/v1/workdays?country=DE&start=&end=` or `&add=10` | Workdays between dates / due date after N workdays | 0.0305 USDC |
| `/v1/payment-cutoff?system=FEDWIRE` | Cut-off times of Fedwire, FedACH, T2, SIC, CHAPS (+ instant systems), minutes left, value date | 0.0345 USDC |
| `/v1/indicators`, `/v1/sources`, `/docs` | Indicator list, source status, docs | free |

Sources: Federal Reserve and ECB meeting calendars, BLS and BEA release schedules, FTSE Russell
announcements, U.S. Treasury Fiscal Data API (public domain), exchange holiday calendars
(`exchange_calendars`), published contract and index rules, the open-source `holidays` library (MIT) and the published
operating hours of the payment systems (Fed, ECB, SNB/SIX, Bank of England). Published schedules can change; every
response carries its source and verification date. Index names are trademarks of their owners; only
dates are provided. Not investment advice.

Tests: `python -m pytest -q`
