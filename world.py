"""A34 Feiertage weltweit (gesetzliche Feiertage je Land/Region, Arbeitstage zählen).

Quelle: Python-Paket «holidays» (MIT-Lizenz, Regeln aus amtlichen Feiertagsgesetzen, lokal berechnet,
kein Netz). Ergebnisse sind gesetzliche Feiertage, keine Bank- oder Börsenfeiertage (dafür A15 bzw. A1).
"""
from __future__ import annotations

import datetime as dt

import holidays

SRC = "Statutory public holidays computed with the open-source 'holidays' library (MIT), version " + holidays.__version__
MAX_SPAN_DAYS = 3 * 366


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _d(s: str | None, name: str) -> dt.date:
    if not s:
        return _today()
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise ValueError(f"'{name}' must be YYYY-MM-DD")


def _cal(country: str, subdiv: str | None, years):
    cc = (country or "").strip().upper()
    if not cc:
        raise ValueError("Parameter 'country' is required (ISO alpha-2, e.g. CH, DE, US)")
    sup = holidays.list_supported_countries()
    if cc not in sup:
        raise KeyError(f"Country '{cc}' not supported. Use an ISO 3166 alpha-2 code.")
    sd = (subdiv or "").strip().upper() or None
    if sd and sd.startswith(cc + "-"):
        sd = sd[len(cc) + 1:]
    if sd and sd not in [s.upper() for s in sup[cc]]:
        raise KeyError(f"Subdivision '{sd}' not supported for {cc}. Supported: {', '.join(sup[cc][:60])}")
    cls = holidays.country_holidays(cc, subdiv=sd, years=years)
    lang = "en_US" if "en_US" in getattr(cls, "supported_languages", ()) else None
    if lang:
        cls = holidays.country_holidays(cc, subdiv=sd, years=years, language=lang)
    return cc, sd, cls, sup[cc]


def public_holidays(country: str, year: int | None = None, subdiv: str | None = None) -> dict:
    y = int(year or _today().year)
    if not 1950 <= y <= 2100:
        raise ValueError("year must be between 1950 and 2100")
    cc, sd, cal, subs = _cal(country, subdiv, y)
    items = [{"date": d.isoformat(), "weekday": d.strftime("%A"), "name": n}
             for d, n in sorted(cal.items()) if d.year == y]
    nxt = None
    today = _today()
    if y >= today.year:
        _, _, cal2, _ = _cal(cc, sd, [today.year, today.year + 1])
        nxt = next(({"date": d.isoformat(), "name": n} for d, n in sorted(cal2.items()) if d >= today), None)
    return {"country": cc, "subdivision": sd, "year": y, "count": len(items),
            "on_weekdays": sum(1 for i in items if dt.date.fromisoformat(i["date"]).weekday() < 5),
            "holidays": items, "next_holiday": nxt, "subdivisions_available": subs[:80], "source": SRC}


def workdays(country: str, start: str | None = None, end: str | None = None, subdiv: str | None = None,
             weekend: str = "sat,sun") -> dict:
    a, b = _d(start, "start"), _d(end, "end")
    if b < a:
        raise ValueError("'end' must not be before 'start'")
    if (b - a).days > MAX_SPAN_DAYS:
        raise ValueError("Range is limited to 3 years")
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    wk = {names.index(x.strip().lower()[:3]) for x in (weekend or "").split(",") if x.strip()}
    if not wk <= set(range(7)):
        raise ValueError("weekend must be a comma list like sat,sun or fri,sat")
    cc, sd, cal, _ = _cal(country, subdiv, list(range(a.year, b.year + 1)))
    work, off = 0, []
    d = a
    while d <= b:
        if d in cal and d.weekday() not in wk:
            off.append({"date": d.isoformat(), "name": cal.get(d)})
        elif d.weekday() not in wk:
            work += 1
        d += dt.timedelta(days=1)
    total = (b - a).days + 1
    return {"country": cc, "subdivision": sd, "start": a.isoformat(), "end": b.isoformat(),
            "calendar_days": total, "workdays": work, "weekend_days": sum(
                1 for i in range(total) if (a + dt.timedelta(days=i)).weekday() in wk),
            "holidays_on_workdays": off, "note": "Both dates inclusive.", "source": SRC}


def add_workdays(country: str, start: str | None, days: int, subdiv: str | None = None) -> dict:
    if abs(days) > 1000:
        raise ValueError("days must be between -1000 and 1000")
    a = _d(start, "start")
    cc, sd, cal, _ = _cal(country, subdiv, list(range(a.year - 4, a.year + 5)))
    step = 1 if days >= 0 else -1
    d, left, skipped = a, abs(days), []
    while left:
        d += dt.timedelta(days=step)
        if d.weekday() >= 5:
            continue
        if d in cal:
            skipped.append({"date": d.isoformat(), "name": cal.get(d)})
            continue
        left -= 1
    return {"country": cc, "subdivision": sd, "start": a.isoformat(), "workdays_added": days,
            "result": d.isoformat(), "weekday": d.strftime("%A"), "holidays_skipped": skipped, "source": SRC}
