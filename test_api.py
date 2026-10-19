"""Tests der Market Calendar API (ohne Netz). Start: python -m pytest -q"""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

import engine
from app import app

c = TestClient(app)

UPCOMING = [
    {"record_date": "2026-10-16", "security_type": "Bill", "security_term": "6-Week", "reopening": "Yes",
     "cusip": "912797VG9", "offering_amt": "null", "announcemt_date": "2026-10-22", "auction_date": "2026-10-27",
     "issue_date": "2026-10-29"},
    {"record_date": "2026-10-16", "security_type": "Note", "security_term": "7-Year", "reopening": "No",
     "cusip": "91282CRV5", "offering_amt": "44000000000", "announcemt_date": "2026-10-22",
     "auction_date": "2026-10-29", "issue_date": "2026-11-02"},
    {"record_date": "2026-10-09", "security_type": "Note", "security_term": "2-Year", "reopening": "No",
     "cusip": "OLD", "offering_amt": "null", "announcemt_date": "2026-10-01", "auction_date": "2026-10-28",
     "issue_date": "2026-11-02"},
]
PAST = [{"record_date": "2026-10-15", "security_type": "Note", "security_term": "5-Year", "cusip": "91282CRR4",
         "auction_date": "2026-10-15", "announcemt_date": "2026-10-08", "issue_date": "2026-10-30",
         "maturity_date": "2031-10-15", "offering_amt": "26000000000", "high_yield": "3.612",
         "bid_to_cover_ratio": "2.41", "int_rate": "3.5", "high_discnt_rate": "null"}]


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    engine._cache.clear()

    def fiscal(ds, params):
        return UPCOMING if ds == "upcoming_auctions" else PAST
    monkeypatch.setattr(engine, "_fiscal", fiscal)

    monkeypatch.setattr(engine, "_today", lambda: dt.date(2026, 10, 19))


def get(path, **p):
    r = c.get(path, params=p)
    assert r.status_code == 200, r.text
    return r.json()


def test_opex_juneteenth_and_triple_witching():
    cal = get("/v1/opex-calendar", year=2026, venue="us")["us_monthly"]
    june = cal[5]
    assert june["date"] == "2026-06-18" and june["holiday_adjusted"] and june["quarterly_triple_witching"]
    r = get("/v1/opex", date="2026-12-18")
    assert r["is_triple_witching"] and r["is_eurex_expiration"]


def test_vix_rule_with_holiday_friday():
    exp = {e["contract_month"]: e["date"] for e in get("/v1/vix-expiry", count=12, date="2026-01-01")["expirations"]}
    assert exp["2026-03"] == "2026-03-18"
    assert exp["2026-05"] == "2026-05-19"  # 3. Freitag Juni = Juneteenth -> 30 Tage vor Donnerstag
    assert get("/v1/opex", date="2026-05-19")["is_vix_expiration"]


def test_eurex_good_friday_2027():
    eu = get("/v1/opex-calendar", year=2027, venue="eurex")["eurex_monthly"]
    assert eu[2]["date"] == "2027-03-19"


def test_releases_and_next():
    r = get("/v1/next-release", indicator="CPI", date="2026-10-19")
    assert r["next"][0]["date"] == "2026-11-10" and r["next"][0]["time"]["utc"] == "2026-11-10T13:30:00Z"
    rows = get("/v1/releases", **{"from": "2026-11-01", "to": "2026-11-30"})["releases"]
    assert [x["indicator"] for x in rows] == ["NFP", "CPI", "PPI", "GDP", "PCE"]
    assert c.get("/v1/next-release", params={"indicator": "XYZ"}).status_code == 404


def test_meetings():
    r = get("/v1/next-meeting", bank="all", date="2026-10-19")
    assert r["next"]["fed"]["decision_date"] == "2026-10-28"
    assert r["next"]["fed"]["statement"]["utc"] == "2026-10-28T18:00:00Z"
    assert r["next"]["ecb"]["statement"]["utc"] == "2026-10-29T13:15:00Z"
    assert len(get("/v1/meetings", bank="ecb", year=2027)["meetings"]) == 8
    assert c.get("/v1/meetings", params={"year": 2025}).status_code == 400


def test_rebalance():
    r = get("/v1/rebalance", index="ALL", year=2026)["indexes"]
    assert r["SP500"]["dates"][1]["effective_after_close"] == "2026-06-18"
    assert r["RUSSELL"]["dates"][1]["effective_after_close"] == "2026-12-11"
    assert r["NDX"]["dates"][3]["type"] == "annual reconstitution"


def test_banking():
    r = get("/v1/is-banking-day", zone="TARGET2", date="2027-03-26")
    assert not r["is_banking_day"] and r["reason"] == "Good Friday" and r["next_banking_day"] == "2027-03-30"
    us = [h["date"] for h in get("/v1/banking-holidays", zone="US", year=2027)["holidays_on_weekdays"]]
    assert "2027-07-05" in us and "2027-06-18" not in us  # Juneteenth Samstag: Fed nicht verschoben
    ch = [h["name"] for h in get("/v1/banking-holidays", zone="CH", year=2027)["holidays_on_weekdays"]]
    assert "Ascension Day" in ch
    assert c.get("/v1/is-banking-day", params={"zone": "XX"}).status_code == 400


def test_auctions():
    r = get("/v1/auctions", **{"from": "2026-10-10", "to": "2026-10-31"})
    terms = [a["security_term"] for a in r["auctions"]]
    assert terms == ["5-Year", "6-Week", "7-Year"]  # nur neuster Stand der Vorschau
    assert r["auctions"][0]["results"]["high_yield"] == 3.612
    assert get("/v1/next-auction", term="7-year")["next"]["cusip"] == "91282CRV5"
    assert get("/v1/sources", check="true")["latest"]["treasury_next_auction"] == "2026-10-27"


def test_briefing(monkeypatch):
    import engine
    monkeypatch.setattr(engine, "auctions", lambda *a, **k: (_ for _ in ()).throw(engine.SourceUnavailable("x")))
    r = c.get("/v1/briefing", params={"date": "2026-10-26", "days": 7})
    assert r.status_code == 200
    j = r.json()
    titles = [x["title"] for x in j["high_importance"]]
    assert "Fed rate decision" in titles and "ECB rate decision" in titles
    assert j["notes"]
    assert c.get("/v1/briefing", params={"days": 99}).status_code == 422
