"""Rechenkern der Market Calendar API.

A3 Optionsverfall (Regeln), A4 US-Konjunkturtermine, A5 Fed/EZB-Sitzungen, A13 Index-Rebalancing,
A14 Treasury-Auktionen (Fiscal Data API), A15 Bank-/Zahlungsfeiertage.
"""
from __future__ import annotations

import datetime as dt
import threading
import time
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import httpx
import pandas as pd

import schedules as S

ET = ZoneInfo("America/New_York")
CET = ZoneInfo("Europe/Berlin")
UTC = dt.timezone.utc
YEARS = range(2020, 2029)
D = dt.date


def _today() -> dt.date:
    return dt.datetime.now(UTC).date()


class SourceUnavailable(RuntimeError):
    pass


def _date(s: str | None, default: dt.date | None = None) -> dt.date:
    if not s:
        return default or _today()
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        raise ValueError("date must be YYYY-MM-DD")


def _year(y) -> int:
    y = int(y)
    if y not in YEARS:
        raise ValueError(f"year must be between {YEARS.start} and {YEARS.stop - 1}")
    return y


@lru_cache(maxsize=8)
def cal(code: str):
    return xcals.get_calendar(code, start="2019-01-01", end="2029-12-31")


def is_session(code: str, d: dt.date) -> bool:
    return bool(cal(code).is_session(pd.Timestamp(d)))


def prev_session(code: str, d: dt.date) -> dt.date:
    """d selbst, falls Handelstag, sonst der Handelstag davor."""
    while not is_session(code, d):
        d -= dt.timedelta(days=1)
    return d


def _iso(d) -> str:
    return d.isoformat()


def third_friday(y: int, m: int) -> dt.date:
    d = dt.date(y, m, 15)
    return d + dt.timedelta(days=(4 - d.weekday()) % 7)


def _at(d: dt.date, hh: int, mm: int, tz) -> dict:
    t = dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz)
    return {"local": t.isoformat(), "utc": t.astimezone(UTC).isoformat().replace("+00:00", "Z")}


# ================================================================== A3 Optionsverfall
def us_monthly_opex(y: int, m: int) -> dict:
    tf = third_friday(y, m)
    d = prev_session("XNYS", tf)
    return {"date": _iso(d), "nominal_third_friday": _iso(tf), "holiday_adjusted": d != tf,
            "quarterly_triple_witching": m in (3, 6, 9, 12)}


def vix_expiry(y: int, m: int) -> dict:
    """Cboe-Regel: Mittwoch 30 Tage vor dem 3. Freitag des Folgemonats; ist dieser Freitag ein Feiertag,
    30 Tage vor dem Handelstag davor; ist der Mittwoch kein Handelstag, der Handelstag davor."""
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    f = prev_session("XNYS", third_friday(ny, nm))
    w = f - dt.timedelta(days=30)
    d = prev_session("XNYS", w)
    return {"contract_month": f"{y}-{m:02d}", "date": _iso(d), "rule_wednesday": _iso(w),
            "holiday_adjusted": d != w,
            "settlement": "Special Opening Quotation (SOQ) of VIX on the morning of the expiration date"}


def eurex_expiry(y: int, m: int) -> dict:
    tf = third_friday(y, m)
    d = prev_session("XETR", tf)
    return {"date": _iso(d), "nominal_third_friday": _iso(tf), "holiday_adjusted": d != tf,
            "quarterly": m in (3, 6, 9, 12),
            "products": "Index options/futures such as ODAX/FDAX, OESX/FESX (final settlement day)"}


def opex_calendar(year, venue: str = "all") -> dict:
    y = _year(year)
    venue = (venue or "all").lower()
    if venue not in ("all", "us", "vix", "eurex"):
        raise ValueError("venue must be all, us, vix or eurex")
    out = {"year": y}
    if venue in ("all", "us"):
        out["us_monthly"] = [us_monthly_opex(y, m) for m in range(1, 13)]
    if venue in ("all", "vix"):
        out["vix"] = [vix_expiry(y, m) for m in range(1, 13)]
    if venue in ("all", "eurex"):
        out["eurex_monthly"] = [eurex_expiry(y, m) for m in range(1, 13)]
    out["notes"] = ["US monthly: 3rd Friday; if an exchange holiday, the preceding business day.",
                    "Quarterly expirations (Mar/Jun/Sep/Dec) are 'triple witching'.",
                    "Eurex: 3rd Friday; if not an exchange day, the preceding exchange day."]
    out["source"] = {"rules": "Cboe, CME and Eurex contract specifications", "holidays": "exchange_calendars"}
    return out


def opex_on(date: str | None = None) -> dict:
    d = _date(date)
    y, m = d.year, d.month
    us = us_monthly_opex(y, m)
    eu = eurex_expiry(y, m)
    vix_today = next((v for v in (vix_expiry(y, m), vix_expiry(*(y, m + 1) if m < 12 else (y + 1, 1)))
                      if v["date"] == _iso(d)), None)
    us_session = is_session("XNYS", d)
    # wöchentliche SPX-/SPY-Verfälle: jeder Freitag, bei Feiertag der Handelstag davor
    fri = d + dt.timedelta(days=(4 - d.weekday()) % 7)
    weekly = prev_session("XNYS", fri)

    def nxt(fn):
        yy, mm = y, m
        for _ in range(14):
            r = fn(yy, mm)
            if r["date"] >= _iso(d):
                return r
            yy, mm = (yy + 1, 1) if mm == 12 else (yy, mm + 1)

    return {"date": _iso(d), "weekday": d.strftime("%A"),
            "is_us_monthly_opex": us["date"] == _iso(d),
            "is_triple_witching": us["date"] == _iso(d) and us["quarterly_triple_witching"],
            "is_us_weekly_expiration": weekly == d and us_session,
            "is_vix_expiration": vix_today is not None,
            "is_eurex_expiration": eu["date"] == _iso(d),
            "us_daily_expirations": us_session,
            "next": {"us_monthly": nxt(us_monthly_opex), "vix": nxt(vix_expiry), "eurex": nxt(eurex_expiry)},
            "note": "SPX/SPY/QQQ also list daily (0DTE) expirations on every US trading day.",
            "source": {"rules": "Cboe, CME and Eurex contract specifications", "holidays": "exchange_calendars"}}


def vix_expiries(count: int = 6, date: str | None = None) -> dict:
    if not 1 <= int(count) <= 24:
        raise ValueError("count must be between 1 and 24")
    d = _date(date)
    y, m = d.year, d.month
    out = []
    while len(out) < int(count):
        v = vix_expiry(y, m)
        if v["date"] >= _iso(d):
            out.append(v)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return {"from": _iso(d), "expirations": out,
            "rule": "Wednesday 30 days before the 3rd Friday of the following month (holiday-adjusted).",
            "source": {"rules": "Cboe VIX futures/options specifications", "holidays": "exchange_calendars"}}


# ================================================================== A4 US-Konjunkturtermine
def indicators() -> list[dict]:
    return [{"indicator": k, "name": v["name"], "agency": v["agency"], "source": v["source"]}
            for k, v in S.RELEASES.items()]


def _release_rows(keys):
    rows = []
    for k in keys:
        r = S.RELEASES[k]
        for d, period in r["dates"]:
            day = dt.date.fromisoformat(d)
            rows.append({"indicator": k, "name": r["name"], "date": d, "reference_period": period,
                         "time": {"et": "08:30", **_at(day, 8, 30, ET)}, "agency": r["agency"],
                         "source": r["source"]})
    return sorted(rows, key=lambda x: (x["date"], x["indicator"]))


def _ind_keys(indicator: str | None):
    if not indicator:
        return list(S.RELEASES)
    keys = [k.strip().upper() for k in indicator.split(",") if k.strip()]
    for k in keys:
        if k not in S.RELEASES:
            raise KeyError(f"Unknown indicator '{k}'. Use one of: {', '.join(S.RELEASES)}")
    return keys


def _last_known(keys):
    return max(r["dates"][-1][0] for k, r in S.RELEASES.items() if k in keys)


def releases(start: str | None = None, end: str | None = None, indicator: str | None = None) -> dict:
    a = _date(start)
    b = _date(end, a + dt.timedelta(days=31))
    if b < a or (b - a).days > 400:
        raise ValueError("end must be after start and at most 400 days later")
    keys = _ind_keys(indicator)
    rows = [r for r in _release_rows(keys) if _iso(a) <= r["date"] <= _iso(b)]
    return {"from": _iso(a), "to": _iso(b), "releases": rows, "known_until": _last_known(keys),
            "verified": S.VERIFIED,
            "note": "Official schedules; dates can change (e.g. during a US government shutdown)."}


def next_release(indicator: str, date: str | None = None) -> dict:
    keys = _ind_keys(indicator)
    d = _iso(_date(date))
    rows = [r for r in _release_rows(keys) if r["date"] >= d]
    if not rows:
        raise ValueError(f"No scheduled release after {d} in the published calendar (known until "
                         f"{_last_known(keys)})")
    first = rows[0]["date"]
    return {"from": d, "next": [r for r in rows if r["date"] == first], "verified": S.VERIFIED}


# ================================================================== A5 Notenbanken
def _meeting_rows(bank: str, year: int | None = None):
    rows = []
    if bank in ("fed", "all"):
        for y, ms in S.FOMC.items():
            if year and y != year:
                continue
            for a, b, sep in ms:
                day = dt.date.fromisoformat(b)
                rows.append({"bank": "Fed", "body": "FOMC", "start": a, "decision_date": b,
                             "statement": _at(day, 14, 0, ET), "press_conference": _at(day, 14, 30, ET),
                             "projections": sep, "tentative": y >= 2027,
                             "source": S.FOMC_SOURCE})
    if bank in ("ecb", "all"):
        for y, ms in S.ECB.items():
            if year and y != year:
                continue
            for a, b, proj in ms:
                day = dt.date.fromisoformat(b)
                rows.append({"bank": "ECB", "body": "Governing Council (monetary policy)", "start": a,
                             "decision_date": b, "statement": _at(day, 14, 15, CET),
                             "press_conference": _at(day, 14, 45, CET), "projections": proj,
                             "tentative": False, "source": S.ECB_SOURCE})
    return sorted(rows, key=lambda r: r["decision_date"])


def _bank(bank: str | None) -> str:
    b = (bank or "all").lower()
    if b not in ("fed", "ecb", "all"):
        raise ValueError("bank must be fed, ecb or all")
    return b


def meetings(bank: str | None = None, year=None) -> dict:
    b = _bank(bank)
    y = _year(year) if year else _today().year
    rows = _meeting_rows(b, y)
    if not rows:
        raise ValueError(f"No published meeting calendar for {y} (available: 2026, 2027)")
    return {"bank": b, "year": y, "meetings": rows, "verified": S.VERIFIED}


def next_meeting(bank: str | None = None, date: str | None = None) -> dict:
    b = _bank(bank)
    d = _iso(_date(date))
    out = {}
    for name in (["fed", "ecb"] if b == "all" else [b]):
        nxt = [r for r in _meeting_rows(name) if r["decision_date"] >= d]
        out[name] = nxt[0] if nxt else None
    return {"from": d, "next": out, "verified": S.VERIFIED}


# ================================================================== A13 Index-Rebalancing
INDEXES = ("SP500", "NDX", "RUSSELL", "DAX")


def rebalance(index: str | None = None, year=None) -> dict:
    y = _year(year) if year else _today().year
    keys = INDEXES if not index or index.upper() == "ALL" else [i.strip().upper() for i in index.split(",")]
    for k in keys:
        if k not in INDEXES:
            raise KeyError(f"Unknown index '{k}'. Use one of: {', '.join(INDEXES)}, ALL")
    out = {}
    for k in keys:
        rows = []
        if k in ("SP500", "NDX", "DAX"):
            code = "XETR" if k == "DAX" else "XNYS"
            for m in (3, 6, 9, 12):
                tf = third_friday(y, m)
                eff = prev_session(code, tf)
                kind = {"SP500": "quarterly rebalance",
                        "NDX": "annual reconstitution" if m == 12 else "quarterly rebalance",
                        "DAX": "quarterly index review (regular)"}[k]
                nxt = eff + dt.timedelta(days=1)
                while not is_session(code, nxt):
                    nxt += dt.timedelta(days=1)
                rows.append({"type": kind, "effective_after_close": _iso(eff),
                             "first_trading_day_new_weights": _iso(nxt)})
            rule = {"SP500": "Effective after the close of the 3rd Friday of Mar/Jun/Sep/Dec.",
                    "NDX": "Annual reconstitution in December, quarterly rebalances in Mar/Jun/Sep; effective after "
                           "the close of the 3rd Friday.",
                    "DAX": "Regular reviews effective after the close of the 3rd Friday of Mar/Jun/Sep/Dec "
                           "(changes apply from the following Monday)."}[k]
            out[k] = {"dates": rows, "rule": rule, "basis": "computed from published index methodology"}
        else:
            rows = [dict(type=f"semi-annual reconstitution ({p[-2:] == '06' and 'June' or 'December'})", period=p,
                         **{kk: vv for kk, vv in v.items() if kk != "source"}, source=v["source"])
                    for p, v in S.RUSSELL.items() if p.startswith(str(y))]
            out[k] = {"dates": rows,
                      "rule": "Russell US indexes reconstitute semi-annually (June and December) from 2026.",
                      "basis": "published FTSE Russell schedule" if rows else
                               f"no published schedule for {y} yet"}
    return {"year": y, "indexes": out, "verified": S.VERIFIED,
            "note": "Dates only. Index names are trademarks of their owners; no index data is provided."}


# ================================================================== A15 Bank-/Zahlungsfeiertage
def easter(y: int) -> dt.date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return dt.date(y, month, day)


def _nth_weekday(y, m, weekday, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(y, m, weekday):
    d = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def target2_holidays(y: int) -> list[dict]:
    e = easter(y)
    return [{"date": _iso(dt.date(y, 1, 1)), "name": "New Year's Day"},
            {"date": _iso(e - dt.timedelta(days=2)), "name": "Good Friday"},
            {"date": _iso(e + dt.timedelta(days=1)), "name": "Easter Monday"},
            {"date": _iso(dt.date(y, 5, 1)), "name": "Labour Day"},
            {"date": _iso(dt.date(y, 12, 25)), "name": "Christmas Day"},
            {"date": _iso(dt.date(y, 12, 26)), "name": "Boxing Day / St Stephen's Day"}]


def us_fed_holidays(y: int) -> list[dict]:
    """Federal Reserve Banks / Fedwire: fällt ein Feiertag auf Sonntag, ist Montag zu; Samstag wird nicht verschoben."""
    rows = [(dt.date(y, 1, 1), "New Year's Day"), (_nth_weekday(y, 1, 0, 3), "Martin Luther King Jr. Day"),
            (_nth_weekday(y, 2, 0, 3), "Washington's Birthday"), (_last_weekday(y, 5, 0), "Memorial Day"),
            (dt.date(y, 6, 19), "Juneteenth"), (dt.date(y, 7, 4), "Independence Day"),
            (_nth_weekday(y, 9, 0, 1), "Labor Day"), (_nth_weekday(y, 10, 0, 2), "Columbus Day"),
            (dt.date(y, 11, 11), "Veterans Day"), (_nth_weekday(y, 11, 3, 4), "Thanksgiving Day"),
            (dt.date(y, 12, 25), "Christmas Day")]
    out = []
    for d, n in rows:
        if d.weekday() == 6:
            out.append({"date": _iso(d + dt.timedelta(days=1)), "name": n + " (observed)"})
        elif d.weekday() == 5:
            continue  # Fed-Banken sind am Freitag davor offen
        else:
            out.append({"date": _iso(d), "name": n})
    return out


def ch_six_holidays(y: int) -> list[dict]:
    c = cal("XSWX")
    days = c.regular_holidays.holidays(f"{y}-01-01", f"{y}-12-31", return_name=True)
    return [{"date": _iso(d.date()), "name": n} for d, n in days.items() if d.weekday() < 5]


ZONES = {
    "TARGET2": ("Euro payments (T2 / SEPA settlement)", target2_holidays,
                "ECB: T2 closing days (New Year, Good Friday, Easter Monday, 1 May, 25 and 26 December)"),
    "US": ("US Federal Reserve Banks / Fedwire", us_fed_holidays, "Federal Reserve holiday schedule rules"),
    "CH": ("Switzerland: SIX Swiss Exchange closing days", ch_six_holidays,
           "exchange_calendars XSWX (SIX trading calendar)"),
}


def _zone(zone: str) -> str:
    z = (zone or "").upper()
    z = "TARGET2" if z in ("T2", "EUR", "EURO") else z
    if z not in ZONES:
        raise ValueError(f"zone must be one of: {', '.join(ZONES)}")
    return z


def banking_holidays(zone: str, year=None) -> dict:
    z = _zone(zone)
    y = _year(year) if year else _today().year
    name, fn, src = ZONES[z]
    rows = [r for r in fn(y) if dt.date.fromisoformat(r["date"]).weekday() < 5]
    return {"zone": z, "description": name, "year": y, "holidays_on_weekdays": rows,
            "note": "Weekends are always closed." + (
                " Swiss banks may also close on 24/31 December afternoons and cantonal holidays."
                if z == "CH" else ""),
            "source": src}


def is_banking_day(zone: str, date: str | None = None) -> dict:
    z = _zone(zone)
    d = _date(date)
    hol = {r["date"]: r["name"] for r in ZONES[z][1](d.year)}
    reason = "weekend" if d.weekday() >= 5 else hol.get(_iso(d))
    nxt = d + dt.timedelta(days=1)
    while nxt.weekday() >= 5 or _iso(nxt) in {r["date"] for r in ZONES[z][1](nxt.year)}:
        nxt += dt.timedelta(days=1)
    return {"zone": z, "date": _iso(d), "is_banking_day": reason is None, "reason": reason,
            "next_banking_day": _iso(nxt), "source": ZONES[z][2]}


# ================================================================== A14 Treasury-Auktionen
FISCAL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/"
UA = {"User-Agent": "MarketCalendarAPI/0.1 (contact: data-api@users.noreply.github.com)"}
_cache: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()
STATUS: dict[str, dict] = {}


def _cached(key, ttl, loader):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    try:
        val = loader()
        with _lock:
            _cache[key] = (now, val)
        STATUS[key] = {"ok": True, "loaded_at": dt.datetime.now(UTC).isoformat()}
        return val
    except Exception as e:
        STATUS[key] = {"ok": False, "error": str(e)[:200], "at": dt.datetime.now(UTC).isoformat()}
        if hit:
            return hit[1]
        raise SourceUnavailable(f"Data source temporarily unavailable ({key}). Please retry later.")


def _fiscal(dataset: str, params: dict) -> list[dict]:
    r = httpx.get(FISCAL + dataset, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def _num(v):
    if v in (None, "", "null"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


RESULT_FIELDS = ["high_yield", "high_discnt_rate", "high_investment_rate", "int_rate", "bid_to_cover_ratio",
                 "total_tendered", "total_accepted", "high_price"]


def _auction_row(r: dict) -> dict:
    res = {k: _num(r.get(k)) for k in RESULT_FIELDS if k in r}
    return {"auction_date": r.get("auction_date"), "security_type": r.get("security_type"),
            "security_term": r.get("security_term"), "cusip": r.get("cusip"),
            "reopening": r.get("reopening"), "announcement_date": r.get("announcemt_date"),
            "issue_date": r.get("issue_date"), "maturity_date": r.get("maturity_date"),
            "offering_amount_usd": _num(r.get("offering_amt")),
            "results": res if any(v is not None for v in res.values()) else None}


def _upcoming() -> list[dict]:
    def load():
        rows = _fiscal("upcoming_auctions", {"sort": "-record_date", "page[size]": "200"})
        if not rows:
            raise ValueError("no upcoming auctions returned")
        latest = max(r.get("record_date", "") for r in rows)
        return [_auction_row(r) for r in rows if r.get("record_date") == latest]
    return _cached("fiscal:upcoming", 1800, load)


def _past(a: dt.date, b: dt.date) -> list[dict]:
    def load():
        rows = _fiscal("auctions_query", {"filter": f"auction_date:gte:{_iso(a)},auction_date:lte:{_iso(b)}",
                                          "sort": "auction_date", "page[size]": "500"})
        return [_auction_row(r) for r in rows]
    return _cached(f"fiscal:past:{a}:{b}", 3600, load)


def _term_match(row, term):
    if not term:
        return True
    t = term.lower().replace(" ", "").replace("-", "")
    s = f"{row.get('security_term') or ''}{row.get('security_type') or ''}".lower().replace(" ", "").replace("-", "")
    return t in s


def auctions(start: str | None = None, end: str | None = None, term: str | None = None) -> dict:
    today = _today()
    a = _date(start, today)
    b = _date(end, a + dt.timedelta(days=14))
    if b < a or (b - a).days > 92:
        raise ValueError("end must be after start and at most 92 days later")
    rows = {}
    if a <= today:
        for r in _past(a, min(b, today)):
            rows[(r["cusip"], r["auction_date"])] = r
    if b >= today - dt.timedelta(days=7):
        for r in _upcoming():
            if r["auction_date"] and _iso(a) <= r["auction_date"] <= _iso(b):
                rows.setdefault((r["cusip"], r["auction_date"]), r)
    out = sorted((r for r in rows.values() if _term_match(r, term)),
                 key=lambda r: (r["auction_date"] or "", r["security_term"] or ""))
    return {"from": _iso(a), "to": _iso(b), "term": term, "auctions": out,
            "note": "Bills/notes/bonds auctions; competitive bids close 11:30 (bills) or 13:00 ET (coupons).",
            "source": "U.S. Treasury Fiscal Data API (upcoming_auctions, auctions_query), public domain"}


def next_auction(term: str | None = None) -> dict:
    today = _iso(_today())
    rows = sorted((r for r in _upcoming() if (r["auction_date"] or "") >= today and _term_match(r, term)),
                  key=lambda r: r["auction_date"])
    if not rows:
        raise ValueError("No upcoming auction announced for this term yet")
    return {"term": term, "next": rows[0], "upcoming_count": len(rows),
            "source": "U.S. Treasury Fiscal Data API (upcoming_auctions), public domain"}


def status() -> dict:
    return STATUS


# ================================================================== A18 Briefing (Paket)
def briefing(date: str | None = None, days: int = 7) -> dict:
    """Alles Termin-Relevante für einen Zeitraum in einem Aufruf, nach Datum sortiert."""
    start = _date(date, _today())
    days = int(days)
    if not 1 <= days <= 31:
        raise ValueError("days must be between 1 and 31")
    end = start + dt.timedelta(days=days - 1)
    inside = lambda s: s and start <= dt.date.fromisoformat(s[:10]) <= end
    ev: list[dict] = []

    def add(d, kind, title, importance, **extra):
        ev.append({"date": d[:10], "type": kind, "title": title, "importance": importance, **extra})

    for r in releases(_iso(start), _iso(end))["releases"]:
        imp = "high" if r["indicator"] in ("CPI", "NFP") else "medium"
        add(r["date"], "economic_release", f"US {r['indicator']} ({r['reference_period']})", imp,
            time_utc=r["time"]["utc"], time_et=r["time"]["et"])
    for y in sorted({start.year, end.year}):
        for m in meetings("all", y)["meetings"]:
            if inside(m["decision_date"]):
                add(m["decision_date"], "central_bank", f"{m['bank']} rate decision", "high",
                    time_utc=m["statement"]["utc"],
                    press_conference_utc=(m.get("press_conference") or {}).get("utc"),
                    projections=m.get("projections"))
        oc = opex_calendar(y)
        for o in oc["us_monthly"]:
            if inside(o["date"]):
                tw = o.get("quarterly_triple_witching")
                add(o["date"], "expiration", "US triple witching" if tw else "US monthly options expiration",
                    "high" if tw else "medium")
        for o in oc["vix"]:
            if inside(o["date"]):
                add(o["date"], "expiration", f"VIX expiration ({o['contract_month']})", "medium")
        for o in oc["eurex_monthly"]:
            if inside(o["date"]):
                add(o["date"], "expiration", "Eurex expiration" + (" (quarterly)" if o.get("quarterly") else ""),
                    "medium")
        for idx, v in rebalance("ALL", y)["indexes"].items():
            for r in v["dates"]:
                for k in ("effective_after_close", "rank_day", "preliminary_lists"):
                    if inside(r.get(k)):
                        add(r[k], "index_rebalance", f"{idx} {r['type']}: {k.replace('_', ' ')}", "medium")
        for zone in ("US", "TARGET2", "CH"):
            for h in banking_holidays(zone, y)["holidays_on_weekdays"]:
                if inside(h["date"]):
                    add(h["date"], "banking_holiday", f"{zone} banking holiday: {h['name']}", "low", zone=zone)
    notes = []
    try:
        for a in auctions(_iso(start), _iso(end))["auctions"]:
            term = a.get("security_term", "")
            if inside(a.get("auction_date")) and ("Year" in term):
                add(a["auction_date"], "treasury_auction", f"US {term} {a.get('security_type', '')} auction".strip(),
                    "medium")
    except SourceUnavailable:
        notes.append("Treasury auctions temporarily unavailable; other sections are complete.")
    ev.sort(key=lambda x: (x["date"], x.get("time_utc") or "99", x["type"]))
    by_day: dict[str, list] = {}
    for x in ev:
        by_day.setdefault(x["date"], []).append(x)
    high = [x for x in ev if x["importance"] == "high"]
    return {"from": _iso(start), "to": _iso(end), "days": days, "event_count": len(ev),
            "high_importance": high, "by_day": by_day, "notes": notes,
            "summary": (f"{len(ev)} events from {_iso(start)} to {_iso(end)}, {len(high)} high importance"
                        + (f"; next: {high[0]['title']} on {high[0]['date']}" if high else "")),
            "sources": "Official BLS/BEA, Fed, ECB calendars; Cboe/CME/Eurex rules; Treasury Fiscal Data API"}
