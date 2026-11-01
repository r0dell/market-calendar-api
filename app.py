"""HTTP-API: Market Calendar API (Optionsverfall, US-Konjunkturtermine, Fed/EZB, Rebalancing,
Treasury-Auktionen, Bank-/Zahlungsfeiertage)."""
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

import cutoffs
import engine as e
import world

app = FastAPI(
    title="Market Calendar API",
    version="0.1.0",
    description=("Trading-relevant calendars for agents: options expirations (US monthly, triple witching, VIX, "
                 "Eurex), US economic releases (CPI, NFP, PPI, GDP, PCE) with times, Fed and ECB meetings, index "
                 "rebalancing dates, US Treasury auctions, banking holidays (TARGET2, US Fedwire, Switzerland), "
                 "public holidays worldwide with workday counting, and payment-system cut-off times."),
)


def _run(fn, *args):
    try:
        return fn(*args)
    except KeyError as ex:
        raise HTTPException(status_code=404, detail=str(ex).strip("'\""))
    except e.SourceUnavailable as ex:
        raise HTTPException(status_code=503, detail=str(ex))
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


# ---------------------------------------------------------------- A3
@app.get("/v1/opex", summary="Is a date an options expiration (US monthly, triple witching, VIX, Eurex)? Next ones.")
def opex(date: Optional[str] = Query(None, examples=["2026-12-18"])):
    return _run(e.opex_on, date)


@app.get("/v1/opex-calendar", summary="All monthly expirations of a year (US, VIX, Eurex)")
def opex_calendar(year: int = Query(..., examples=[2027]), venue: str = Query("all", examples=["us"])):
    return _run(e.opex_calendar, year, venue)


@app.get("/v1/vix-expiry", summary="Next VIX futures/options expirations")
def vix_expiry(count: int = Query(6, ge=1, le=24), date: Optional[str] = None):
    return _run(e.vix_expiries, count, date)


# ---------------------------------------------------------------- A4
@app.get("/v1/next-release", summary="Next scheduled release of a US economic indicator with time")
def next_release(indicator: str = Query(..., examples=["CPI"]), date: Optional[str] = None):
    return _run(e.next_release, indicator, date)


@app.get("/v1/releases", summary="US economic releases in a date range")
def releases(frm: Optional[str] = Query(None, alias="from", examples=["2026-11-01"]),
             to: Optional[str] = Query(None, examples=["2026-11-30"]), indicator: Optional[str] = None):
    return _run(e.releases, frm, to, indicator)


@app.get("/v1/indicators", summary="Indicators available for /v1/releases (free)")
def indicators():
    return e.indicators()


# ---------------------------------------------------------------- A5
@app.get("/v1/next-meeting", summary="Next Fed (FOMC) and/or ECB monetary policy decision with times")
def next_meeting(bank: str = Query("all", examples=["fed"]), date: Optional[str] = None):
    return _run(e.next_meeting, bank, date)


@app.get("/v1/meetings", summary="All Fed/ECB monetary policy meetings of a year")
def meetings(bank: str = Query("all"), year: Optional[int] = Query(None, examples=[2027])):
    return _run(e.meetings, bank, year)


# ---------------------------------------------------------------- A13
@app.get("/v1/rebalance", summary="Index rebalancing/reconstitution dates (S&P 500, Nasdaq-100, Russell, DAX)")
def rebalance(index: str = Query("ALL", examples=["RUSSELL"]), year: Optional[int] = Query(None, examples=[2026])):
    return _run(e.rebalance, index, year)


# ---------------------------------------------------------------- A14
@app.get("/v1/auctions", summary="US Treasury auctions in a date range (upcoming and results)")
def auctions(frm: Optional[str] = Query(None, alias="from"), to: Optional[str] = None,
             term: Optional[str] = Query(None, examples=["10-Year"])):
    return _run(e.auctions, frm, to, term)


@app.get("/v1/next-auction", summary="Next announced US Treasury auction (optionally for a term)")
def next_auction(term: Optional[str] = Query(None, examples=["2-Year"])):
    return _run(e.next_auction, term)


# ---------------------------------------------------------------- A15
@app.get("/v1/is-banking-day", summary="Is a date a banking/settlement day in TARGET2, US or CH?")
def is_banking_day(zone: str = Query(..., examples=["TARGET2"]), date: Optional[str] = None):
    return _run(e.is_banking_day, zone, date)


@app.get("/v1/banking-holidays", summary="Banking/settlement holidays of a year for TARGET2, US or CH")
def banking_holidays(zone: str = Query(..., examples=["CH"]), year: Optional[int] = None):
    return _run(e.banking_holidays, zone, year)


# ---------------------------------------------------------------- A18 Paket
@app.get("/v1/briefing", summary="Trading briefing: all scheduled market events for the next days in one call")
def briefing(date: Optional[str] = Query(None, examples=["2026-10-19"]), days: int = Query(7, ge=1, le=31)):
    return _run(e.briefing, date, days)


# ---------------------------------------------------------------- A34 Feiertage weltweit
@app.get("/v1/public-holidays", summary="A34: Statutory public holidays of a country/region for a year")
def public_holidays(country: str = Query(..., examples=["CH"]), year: Optional[int] = None,
                    subdiv: Optional[str] = Query(None, examples=["ZH"])):
    return _run(world.public_holidays, country, year, subdiv)


@app.get("/v1/workdays", summary="A34: Count workdays between two dates, or add N workdays to a date")
def workdays(country: str = Query(..., examples=["DE"]), start: Optional[str] = None, end: Optional[str] = None,
             add: Optional[int] = None, subdiv: Optional[str] = None, weekend: str = "sat,sun"):
    if add is not None:
        return _run(world.add_workdays, country, start, add, subdiv)
    return _run(world.workdays, country, start, end, subdiv, weekend)


# ---------------------------------------------------------------- A35 Zahlungs-Cut-offs
@app.get("/v1/payment-cutoff", summary="A35: Cut-off times of a payment system (Fedwire, ACH, T2, SIC, CHAPS...)")
def payment_cutoff(system: str = Query("all", examples=["FEDWIRE"]), date: Optional[str] = None,
                   at: Optional[str] = None):
    if system.lower() == "all":
        return _run(cutoffs.cutoff_all, date, at)
    return _run(cutoffs.cutoff, system, date, at)


# ---------------------------------------------------------------- frei
@app.get("/v1/sources", summary="Data source status (free)")
def sources(check: bool = False):
    latest = {}
    if check:
        try:
            nxt = e.next_auction()
            latest["treasury_next_auction"] = nxt["next"]["auction_date"]
        except Exception as ex:
            latest["treasury_next_auction"] = f"error: {ex}"[:200]
    from schedules import VERIFIED
    return {"schedules_verified": VERIFIED, "latest": latest, "status": e.status()}


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True}
