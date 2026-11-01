"""A35 Zahlungs-Cut-off-Zeiten (Annahmeschluss) der grossen Zahlungssysteme, inkl. Betriebstage.

Zeiten aus den veröffentlichten Betriebszeiten der Systembetreiber (Stand 1.11.2026, siehe SOURCES).
Betriebstage: TARGET2-/Fed-/SIX-Kalender aus engine.py, UK-Bankfeiertage (England & Wales) aus «holidays».
Banken setzen für ihre Kunden meist frühere interne Fristen; das sagt jede Antwort dazu.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import holidays

import engine

VERIFIED = "2026-11-01"
SYSTEMS = {
    "FEDWIRE": {
        "name": "Fedwire Funds Service (USD RTGS)", "tz": "America/New_York", "calendar": "US",
        "opens_prev_day": "21:00",
        "cutoffs": [("customer_transfers", "18:45"), ("bank_transfers", "19:00")],
        "source": "frbservices.org - Fedwire Funds Service operating hours",
    },
    "FEDACH": {
        "name": "FedACH (USD ACH, Same Day ACH windows)", "tz": "America/New_York", "calendar": "US",
        "cutoffs": [("same_day_window_1", "10:30"), ("same_day_window_2", "14:45"),
                    ("same_day_window_3", "16:45")],
        "settlement": {"same_day_window_1": "13:00", "same_day_window_2": "17:00", "same_day_window_3": "18:00"},
        "note": "Files after 16:45 ET settle next business day at 08:30 ET (last next-day deadline 02:15 ET).",
        "source": "frbservices.org - FedACH processing schedule",
    },
    "T2": {
        "name": "T2 / TARGET (EUR RTGS, Eurosystem)", "tz": "Europe/Berlin", "calendar": "TARGET2",
        "cutoffs": [("customer_payments", "17:00"), ("interbank_payments", "18:00")],
        "source": "ECB - T2 operating schedule",
    },
    "SIC": {
        "name": "SIC (CHF RTGS, Swiss Interbank Clearing)", "tz": "Europe/Zurich", "calendar": "CH",
        "cutoffs": [("customer_payments_clearing_stop_1", "17:00"), ("interbank_clearing_stop_2", "18:00")],
        "note": "SIC instant payments (SIC5) run 24/7.",
        "source": "SNB/SIX - SIC report and disclosure (clearing stops since 15 May 2017)",
    },
    "CHAPS": {
        "name": "CHAPS (GBP RTGS, Bank of England)", "tz": "Europe/London", "calendar": "UK",
        "opens": "06:00",
        "cutoffs": [("customer_payments", "17:40"), ("interbank_payments", "18:00")],
        "note": "Bank of England plans an earlier 01:30 start (targeted September 2027).",
        "source": "Bank of England / Pay.UK - CHAPS operating hours",
    },
    "SEPA_INST": {
        "name": "SEPA Instant Credit Transfer (TIPS / RT1)", "tz": "Europe/Berlin", "calendar": None,
        "cutoffs": [], "note": "24/7/365, settles within seconds; no cut-off.",
        "source": "EPC SCT Inst scheme / ECB TIPS",
    },
    "FEDNOW": {
        "name": "FedNow (USD instant)", "tz": "America/New_York", "calendar": None,
        "cutoffs": [], "note": "24/7/365 instant payments; no cut-off.",
        "source": "frbservices.org - FedNow Service",
    },
}
ALIASES = {"TARGET2": "T2", "TARGET": "T2", "EUR": "T2", "SEPA": "T2", "USD": "FEDWIRE", "WIRE": "FEDWIRE",
           "ACH": "FEDACH", "CHF": "SIC", "GBP": "CHAPS", "TIPS": "SEPA_INST", "SCT_INST": "SEPA_INST",
           "INSTANT": "SEPA_INST"}


def _system(s: str) -> str:
    k = (s or "").strip().upper().replace("-", "_").replace(" ", "_")
    k = ALIASES.get(k, k)
    if k not in SYSTEMS:
        raise KeyError(f"Unknown system '{s}'. Use one of: {', '.join(SYSTEMS)}")
    return k


def _uk_holidays(y: int) -> dict:
    return holidays.country_holidays("GB", subdiv="ENG", years=y)


def _is_operating(cal: str | None, d: dt.date) -> tuple[bool, str | None]:
    if cal is None:
        return True, None
    if d.weekday() >= 5:
        return False, "weekend"
    if cal == "UK":
        h = _uk_holidays(d.year)
        return (False, h.get(d)) if d in h else (True, None)
    r = engine.is_banking_day(cal, d.isoformat())
    return r["is_banking_day"], r["reason"]


def _next_operating(cal, d: dt.date) -> dt.date:
    n = d + dt.timedelta(days=1)
    while not _is_operating(cal, n)[0]:
        n += dt.timedelta(days=1)
    return n


def _at(d: dt.date, hhmm: str, tz: ZoneInfo) -> dt.datetime:
    h, m = map(int, hhmm.split(":"))
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=tz)


def _parse_now(at: str | None) -> dt.datetime:
    if not at:
        return dt.datetime.now(dt.timezone.utc)
    try:
        t = dt.datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("'at' must be an ISO time with offset, e.g. 2026-11-02T16:30:00+01:00 or ...Z")
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t


def cutoff(system: str, date: str | None = None, at: str | None = None) -> dict:
    """Cut-offs eines Systems für einen Tag. Ohne date: heutiger Tag im System, mit Restzeit ab 'at' (Standard jetzt)."""
    k = _system(system)
    s = SYSTEMS[k]
    tz = ZoneInfo(s["tz"])
    now = _parse_now(at)
    if date:
        try:
            d = dt.date.fromisoformat(date)
        except ValueError:
            raise ValueError("'date' must be YYYY-MM-DD")
    else:
        d = now.astimezone(tz).date()
    ok, reason = _is_operating(s["calendar"], d)
    out = {"system": k, "name": s["name"], "date": d.isoformat(), "time_zone": s["tz"],
           "is_operating_day": ok, "closed_reason": reason}
    if not s["cutoffs"]:
        out.update(always_open=True, note=s.get("note"))
    else:
        rows = []
        for label, hhmm in s["cutoffs"]:
            t = _at(d, hhmm, tz)
            row = {"type": label, "local_time": hhmm, "utc": t.astimezone(dt.timezone.utc).isoformat()}
            if ok:
                left = (t - now).total_seconds() / 60
                row["minutes_left"] = round(left) if left > 0 else 0
                row["passed"] = left <= 0
            if "settlement" in s and label in s["settlement"]:
                row["settles_local"] = s["settlement"][label]
            rows.append(row)
        out["cutoffs"] = rows
        if "opens_prev_day" in s:
            out["opens"] = f"{s['opens_prev_day']} local on the previous calendar day"
        elif "opens" in s:
            out["opens"] = f"{s['opens']} local"
        idx = -1 if k == "FEDACH" else 0
        last = _at(d, s["cutoffs"][idx][1], tz)
        if not ok or now >= last:
            out["next_value_date_for_customer_payments"] = _next_operating(s["calendar"], d).isoformat()
        else:
            out["next_value_date_for_customer_payments"] = d.isoformat()
        if s.get("note"):
            out["note"] = s["note"]
    out["caveat"] = "System cut-offs; banks usually set earlier internal deadlines for their clients."
    out["source"] = f"{s['source']} (verified {VERIFIED})"
    return out


def cutoff_all(date: str | None = None, at: str | None = None) -> dict:
    return {"systems": [cutoff(k, date, at) for k in SYSTEMS], "verified": VERIFIED}
