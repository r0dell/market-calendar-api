# Market Calendar API (v0.1)

Trading-relevant calendars for AI agents, paid per call via x402 (USDC on Base).

| Endpoint | Returns | Price |
|---|---|---|
| `/v1/opex?date=` | Is the date a US monthly / triple witching / weekly / VIX / Eurex expiration; next ones | 0.0010 USDC |
| `/v1/opex-calendar?year=&venue=` | All monthly expirations of a year (US, VIX, Eurex), holiday-adjusted | 0.0010 USDC |
| `/v1/vix-expiry?count=` | Next VIX futures/options expirations | 0.0010 USDC |
| `/v1/next-release?indicator=CPI` | Next CPI / NFP / PPI / GDP / PCE release with time (ET, UTC) | 0.0011 USDC |
| `/v1/releases?from=&to=` | US economic releases in a date range | 0.0011 USDC |
| `/v1/next-meeting?bank=fed` | Next Fed (FOMC) / ECB decision with statement and press conference times | 0.0012 USDC |
| `/v1/meetings?bank=&year=` | All Fed/ECB meetings of a year | 0.0012 USDC |
| `/v1/auctions?from=&to=&term=` | US Treasury auctions: upcoming and results | 0.0013 USDC |
| `/v1/next-auction?term=` | Next announced Treasury auction | 0.0013 USDC |
| `/v1/is-banking-day?zone=TARGET2` | Banking/settlement day for TARGET2, US (Fedwire) or CH | 0.0014 USDC |
| `/v1/banking-holidays?zone=&year=` | Banking holidays of a year | 0.0014 USDC |
| `/v1/rebalance?index=&year=` | S&P 500, Nasdaq-100, Russell (semi-annual), DAX rebalancing dates | 0.0020 USDC |
| `/v1/indicators`, `/v1/sources`, `/docs` | Indicator list, source status, docs | free |

Sources: Federal Reserve and ECB meeting calendars, BLS and BEA release schedules, FTSE Russell
announcements, U.S. Treasury Fiscal Data API (public domain), exchange holiday calendars
(`exchange_calendars`), published contract and index rules. Published schedules can change; every
response carries its source and verification date. Index names are trademarks of their owners; only
dates are provided. Not investment advice.

Tests: `python -m pytest -q`
