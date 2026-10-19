"""Market Calendar API mit x402-Bezahlung (USDC auf Base).

Umgebungsvariablen:
  PAY_TO              Deine Wallet-Adresse (0x...), hierhin gehen die Zahlungen. Pflicht.
  X402_NETWORK        "testnet" (Base Sepolia, Standard) oder "mainnet" (Base).
  CDP_API_KEY_ID      Coinbase-Developer-Platform-Key. Für mainnet und Bazaar-Listing nötig.
  CDP_API_KEY_SECRET  dazugehöriges Secret.
  PUBLIC_URL          Öffentliche https-Adresse des Dienstes (für die Bazaar-Beschreibung).

Start:  uvicorn paid_app:app --host 0.0.0.0 --port 8000
Gratis:  /v1/indicators, /v1/sources, /health, /docs
Bezahlt: briefing, opex, opex-calendar, vix-expiry, next-release, releases, next-meeting, meetings,
         rebalance, auctions, next-auction, is-banking-day, banking-holidays
"""
import os
import re

from x402 import x402ResourceServer
from x402.extensions.bazaar import (
    OutputConfig,
    bazaar_resource_server_extension,
    declare_discovery_extension,
)
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import PaymentOption, RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme

from app import app

NETWORKS = {"testnet": "eip155:84532", "mainnet": "eip155:8453"}
TESTNET_FACILITATOR = os.environ.get("FACILITATOR_URL", "https://x402.org/facilitator")

PAY_TO = os.environ.get("PAY_TO", "").strip()
if not re.fullmatch(r"0x[0-9a-fA-F]{40}", PAY_TO):
    raise SystemExit("PAY_TO fehlt oder ist keine gültige Wallet-Adresse (0x + 40 Hex-Zeichen).")

MODE = os.environ.get("X402_NETWORK", "testnet").lower()
if MODE not in NETWORKS:
    raise SystemExit("X402_NETWORK muss 'testnet' oder 'mainnet' sein.")
NETWORK = NETWORKS[MODE]

CDP_ID = os.environ.get("CDP_API_KEY_ID", "").strip().strip('"\'').strip()
CDP_SECRET = os.environ.get("CDP_API_KEY_SECRET", "").strip().strip('"\'').strip()
if "BEGIN" in CDP_SECRET:
    CDP_SECRET = CDP_SECRET.replace("\\n", "\n")  # PEM aus einzeiligem Feld


def _describe_cdp_keys() -> str:
    """Format der Keys beschreiben, ohne Werte preiszugeben."""
    id_kind = ("uuid" if re.fullmatch(r"[0-9a-fA-F-]{36}", CDP_ID)
               else "organizations-path" if CDP_ID.startswith("organizations/") else "other")
    if "BEGIN EC PRIVATE KEY" in CDP_SECRET:
        sec_kind = "ec-pem"
    else:
        try:
            import base64
            sec_kind = f"base64-{len(base64.b64decode(CDP_SECRET, validate=True))}bytes"
        except Exception:
            sec_kind = "unparseable"
    return f"CDP key: id={id_kind} (len {len(CDP_ID)}), secret={sec_kind} (len {len(CDP_SECRET)})"


if CDP_ID and CDP_SECRET:
    from cdp.x402 import create_facilitator_config
    print(_describe_cdp_keys(), flush=True)
    facilitator_cfg = create_facilitator_config(CDP_ID, CDP_SECRET)
elif MODE == "mainnet":
    raise SystemExit("Für mainnet werden CDP_API_KEY_ID und CDP_API_KEY_SECRET benötigt.")
else:
    facilitator_cfg = FacilitatorConfig(url=TESTNET_FACILITATOR)

server = x402ResourceServer(HTTPFacilitatorClient(facilitator_cfg))
server.register(NETWORK, ExactEvmServerScheme())
server.register_extension(bazaar_resource_server_extension)

SVC = "Market Calendar API"


def pay(price: str) -> PaymentOption:
    return PaymentOption(scheme="exact", pay_to=PAY_TO, price=price, network=NETWORK)


def route(price, desc, tags, inp, schema, required, example):
    return RouteConfig(
        accepts=pay(price), description=desc, mime_type="application/json", service_name=SVC, tags=tags,
        extensions=declare_discovery_extension(
            input=inp, input_schema={"properties": schema, "required": required},
            output=OutputConfig(example=example)))


S = lambda d: {"type": "string", "description": d}
DATE = S("Date YYYY-MM-DD. Default: today.")
YEAR = S("Year, e.g. 2027")

# Preise je Agent (eindeutig, damit der Monitor zuordnen kann), seit 19.10.2026 x10:
# A3 0.010, A4 0.011, A5 0.012, A14 0.013, A15 0.014, A13 0.020, A18 Briefing 0.030 USDC
A3, A4, A5, A14, A15, A13, A18 = "$0.01", "$0.011", "$0.012", "$0.013", "$0.014", "$0.02", "$0.03"
routes = {
    "GET /v1/briefing": route(
        A18, "Trading briefing in one call: every scheduled market-moving event for the next 1-31 days, sorted by "
             "date with UTC times and importance - US economic releases (CPI, NFP, PPI, GDP, PCE), Fed and ECB "
             "rate decisions, options expirations (US monthly, triple witching, VIX, Eurex), index rebalancing, "
             "US Treasury coupon auctions and banking holidays (US, TARGET2, Switzerland).",
        ["finance", "trading", "calendar", "briefing", "macro", "economics"], {"days": "7"},
        {"date": DATE, "days": S("Number of days from date, 1-31. Default 7.")}, [],
        {"from": "2026-10-19", "to": "2026-10-25", "event_count": 3,
         "summary": "3 events, 1 high importance; next: Fed rate decision on 2026-10-28",
         "high_importance": [{"date": "2026-10-28", "type": "central_bank", "title": "Fed rate decision",
                              "time_utc": "2026-10-28T18:00:00Z"}]}),
    "GET /v1/opex": route(
        A3, "Tells whether a date is a US monthly options expiration, triple witching, weekly expiration, VIX "
            "expiration or Eurex expiration (holiday-adjusted), and returns the next ones.",
        ["finance", "options", "expiration", "calendar"], {"date": "2026-12-18"}, {"date": DATE}, [],
        {"date": "2026-12-18", "is_us_monthly_opex": True, "is_triple_witching": True,
         "next": {"vix": {"date": "2027-01-20"}}}),
    "GET /v1/opex-calendar": route(
        A3, "Returns all monthly options expiration dates of a year for US equity options, VIX and Eurex, "
            "holiday-adjusted, with triple witching flags.",
        ["finance", "options", "expiration", "calendar"], {"year": "2027", "venue": "all"},
        {"year": YEAR, "venue": S("all, us, vix or eurex")}, ["year"],
        {"year": 2027, "us_monthly": [{"date": "2027-01-15", "quarterly_triple_witching": False}]}),
    "GET /v1/vix-expiry": route(
        A3, "Returns the next VIX futures and options expiration dates (Wednesday rule, holiday-adjusted).",
        ["finance", "vix", "volatility", "expiration"], {"count": "6"},
        {"count": S("Number of expirations, 1-24. Default 6."), "date": DATE}, [],
        {"expirations": [{"contract_month": "2026-11", "date": "2026-11-18"}]}),
    "GET /v1/next-release": route(
        A4, "Returns the next scheduled release of a US economic indicator (CPI, NFP, PPI, GDP, PCE) with exact "
            "time in ET and UTC and the reference period, from official BLS/BEA calendars.",
        ["finance", "economics", "calendar", "macro"], {"indicator": "CPI"},
        {"indicator": S("CPI, NFP, PPI, GDP or PCE; comma list allowed"), "date": DATE}, ["indicator"],
        {"next": [{"indicator": "CPI", "date": "2026-11-10", "reference_period": "October 2026",
                   "time": {"et": "08:30", "utc": "2026-11-10T13:30:00Z"}}]}),
    "GET /v1/releases": route(
        A4, "Lists scheduled US economic releases (CPI, NFP, PPI, GDP, PCE) in a date range with times in ET "
            "and UTC.",
        ["finance", "economics", "calendar", "macro"], {"from": "2026-11-01", "to": "2026-11-30"},
        {"from": DATE, "to": S("End date YYYY-MM-DD, max 400 days after start"),
         "indicator": S("Optional filter: CPI, NFP, PPI, GDP, PCE")}, [],
        {"releases": [{"indicator": "NFP", "date": "2026-11-06"}]}),
    "GET /v1/next-meeting": route(
        A5, "Returns the next Federal Reserve (FOMC) and/or ECB monetary policy decision with statement and press "
            "conference times in local time and UTC, and whether projections are published.",
        ["finance", "central-banks", "fomc", "ecb", "calendar"], {"bank": "all"},
        {"bank": S("fed, ecb or all"), "date": DATE}, [],
        {"next": {"fed": {"decision_date": "2026-10-28", "statement": {"utc": "2026-10-28T18:00:00Z"}}}}),
    "GET /v1/meetings": route(
        A5, "Lists all Fed (FOMC) and ECB monetary policy meetings of a year with decision and press conference "
            "times.",
        ["finance", "central-banks", "fomc", "ecb", "calendar"], {"bank": "all", "year": "2027"},
        {"bank": S("fed, ecb or all"), "year": YEAR}, [],
        {"year": 2027, "meetings": [{"bank": "Fed", "decision_date": "2027-01-27"}]}),
    "GET /v1/rebalance": route(
        A13, "Returns index rebalancing and reconstitution dates (S&P 500, Nasdaq-100, Russell US semi-annual, "
             "DAX reviews) for a year: effective-after-close date and first trading day with new weights.",
        ["finance", "indexes", "rebalancing", "calendar"], {"index": "ALL", "year": "2026"},
        {"index": S("SP500, NDX, RUSSELL, DAX or ALL"), "year": YEAR}, [],
        {"indexes": {"RUSSELL": {"dates": [{"rank_day": "2026-10-30", "effective_after_close": "2026-12-11"}]}}}),
    "GET /v1/auctions": route(
        A14, "Lists US Treasury auctions (bills, notes, bonds, TIPS, FRNs) in a date range: announced upcoming "
             "auctions and results of past ones (high yield/rate, bid-to-cover).",
        ["finance", "treasury", "auctions", "bonds"], {"from": "2026-10-19", "to": "2026-11-02"},
        {"from": DATE, "to": S("End date, max 92 days after start"), "term": S("Optional, e.g. 10-Year, 4-Week")},
        [], {"auctions": [{"auction_date": "2026-10-29", "security_term": "7-Year", "security_type": "Note"}]}),
    "GET /v1/next-auction": route(
        A14, "Returns the next announced US Treasury auction, optionally for a term such as 2-Year or 13-Week.",
        ["finance", "treasury", "auctions", "bonds"], {"term": "10-Year"},
        {"term": S("Optional term, e.g. 2-Year, 10-Year, 13-Week")}, [],
        {"next": {"auction_date": "2026-11-10", "security_term": "10-Year"}}),
    "GET /v1/is-banking-day": route(
        A15, "Tells whether a date is a banking/settlement day for euro payments (TARGET2/SEPA), US Fedwire or "
             "Switzerland (SIX), with the reason and the next banking day.",
        ["finance", "payments", "holidays", "calendar"], {"zone": "TARGET2", "date": "2027-03-26"},
        {"zone": S("TARGET2, US or CH"), "date": DATE}, ["zone"],
        {"zone": "TARGET2", "date": "2027-03-26", "is_banking_day": False, "reason": "Good Friday"}),
    "GET /v1/banking-holidays": route(
        A15, "Lists the banking/settlement holidays of a year for TARGET2 (euro), US Fedwire or Switzerland (SIX).",
        ["finance", "payments", "holidays", "calendar"], {"zone": "CH", "year": "2027"},
        {"zone": S("TARGET2, US or CH"), "year": YEAR}, ["zone"],
        {"zone": "CH", "holidays_on_weekdays": [{"date": "2027-05-06", "name": "Ascension Day"}]}),
}

app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
app.title = f"Market Calendar API ({MODE})"
