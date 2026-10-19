"""Veröffentlichte Termine (von Hand aus den offiziellen Kalendern übernommen).

Jeder Block nennt Quelle und Prüfdatum. Termine können sich ändern (z. B. bei einem US-Shutdown),
deshalb liefert die API immer "verified" und "source" mit.
"""

VERIFIED = "2026-10-19"

# ------------------------------------------------------------------ A5 Notenbanken
# Federal Reserve, https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
# (start, end, sep) – sep = Summary of Economic Projections. 2027 laut Fed vorläufig.
FOMC = {
    2026: [("2026-01-27", "2026-01-28", False), ("2026-03-17", "2026-03-18", True),
           ("2026-04-28", "2026-04-29", False), ("2026-06-16", "2026-06-17", True),
           ("2026-07-28", "2026-07-29", False), ("2026-09-15", "2026-09-16", True),
           ("2026-10-27", "2026-10-28", False), ("2026-12-08", "2026-12-09", True)],
    2027: [("2027-01-26", "2027-01-27", False), ("2027-03-16", "2027-03-17", True),
           ("2027-04-27", "2027-04-28", False), ("2027-06-08", "2027-06-09", True),
           ("2027-07-27", "2027-07-28", False), ("2027-09-14", "2027-09-15", True),
           ("2027-10-26", "2027-10-27", False), ("2027-12-07", "2027-12-08", True)],
}
FOMC_SOURCE = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

# Europäische Zentralbank, https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html
# (Tag 1, Tag 2 = Entscheid + Pressekonferenz, projections)
ECB = {
    2026: [("2026-02-04", "2026-02-05", False), ("2026-03-18", "2026-03-19", True),
           ("2026-04-29", "2026-04-30", False), ("2026-06-10", "2026-06-11", True),
           ("2026-07-22", "2026-07-23", False), ("2026-09-09", "2026-09-10", True),
           ("2026-10-28", "2026-10-29", False), ("2026-12-16", "2026-12-17", True)],
    2027: [("2027-02-03", "2027-02-04", False), ("2027-03-17", "2027-03-18", True),
           ("2027-04-28", "2027-04-29", False), ("2027-06-09", "2027-06-10", True),
           ("2027-07-21", "2027-07-22", False), ("2027-09-08", "2027-09-09", True),
           ("2027-10-27", "2027-10-28", False), ("2027-12-15", "2027-12-16", True)],
}
ECB_SOURCE = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"

# ------------------------------------------------------------------ A4 US-Konjunkturdaten (alle 08:30 ET)
# BLS: https://www.bls.gov/schedule/news_release/{cpi,empsit,ppi}.htm
# BEA: https://www.bea.gov/news/schedule  und  /news/schedule/next-year
RELEASES = {
    "CPI": {
        "name": "Consumer Price Index", "agency": "BLS",
        "source": "https://www.bls.gov/schedule/news_release/cpi.htm",
        "dates": [("2026-11-10", "October 2026"), ("2026-12-10", "November 2026"),
                  ("2027-01-13", "December 2026"), ("2027-02-11", "January 2027"),
                  ("2027-03-10", "February 2027"), ("2027-04-13", "March 2027"),
                  ("2027-05-12", "April 2027"), ("2027-06-10", "May 2027"),
                  ("2027-07-14", "June 2027"), ("2027-08-11", "July 2027"),
                  ("2027-09-14", "August 2027"), ("2027-10-14", "September 2027"),
                  ("2027-11-10", "October 2027"), ("2027-12-10", "November 2027")]},
    "NFP": {
        "name": "Employment Situation (Nonfarm Payrolls, unemployment rate)", "agency": "BLS",
        "source": "https://www.bls.gov/schedule/news_release/empsit.htm",
        "dates": [("2026-11-06", "October 2026"), ("2026-12-04", "November 2026"),
                  ("2027-01-08", "December 2026"), ("2027-02-05", "January 2027"),
                  ("2027-03-05", "February 2027"), ("2027-04-02", "March 2027"),
                  ("2027-05-07", "April 2027"), ("2027-06-04", "May 2027"),
                  ("2027-07-02", "June 2027"), ("2027-08-06", "July 2027"),
                  ("2027-09-03", "August 2027"), ("2027-10-08", "September 2027"),
                  ("2027-11-05", "October 2027"), ("2027-12-03", "November 2027")]},
    "PPI": {
        "name": "Producer Price Index", "agency": "BLS",
        "source": "https://www.bls.gov/schedule/news_release/ppi.htm",
        "dates": [("2026-11-13", "October 2026"), ("2026-12-15", "November 2026"),
                  ("2027-01-14", "December 2026"), ("2027-02-12", "January 2027"),
                  ("2027-03-12", "February 2027"), ("2027-04-14", "March 2027"),
                  ("2027-05-13", "April 2027"), ("2027-06-11", "May 2027"),
                  ("2027-07-15", "June 2027"), ("2027-08-10", "July 2027"),
                  ("2027-09-10", "August 2027"), ("2027-10-15", "September 2027"),
                  ("2027-11-12", "October 2027"), ("2027-12-15", "November 2027")]},
    "GDP": {
        "name": "Gross Domestic Product", "agency": "BEA",
        "source": "https://www.bea.gov/news/schedule",
        "dates": [("2026-10-29", "Q3 2026 advance"), ("2026-11-25", "Q3 2026 second"),
                  ("2026-12-23", "Q3 2026 third"), ("2027-01-28", "Q4 2026 advance"),
                  ("2027-02-25", "Q4 2026 second"), ("2027-03-31", "Q4 2026 third"),
                  ("2027-04-29", "Q1 2027 advance"), ("2027-05-27", "Q1 2027 second"),
                  ("2027-06-25", "Q1 2027 third"), ("2027-07-29", "Q2 2027 advance"),
                  ("2027-08-25", "Q2 2027 second"), ("2027-09-30", "Q2 2027 third"),
                  ("2027-10-28", "Q3 2027 advance"), ("2027-11-24", "Q3 2027 second"),
                  ("2027-12-22", "Q3 2027 third")]},
    "PCE": {
        "name": "Personal Income and Outlays (PCE price index)", "agency": "BEA",
        "source": "https://www.bea.gov/news/schedule",
        "dates": [("2026-10-29", "September 2026"), ("2026-11-25", "October 2026"),
                  ("2026-12-23", "November 2026"), ("2027-01-28", "December 2026"),
                  ("2027-02-25", "January 2027"), ("2027-03-31", "February 2027"),
                  ("2027-04-29", "March 2027"), ("2027-05-27", "April 2027"),
                  ("2027-06-25", "May 2027"), ("2027-07-29", "June 2027"),
                  ("2027-08-25", "July 2027"), ("2027-09-30", "August 2027"),
                  ("2027-10-28", "September 2027"), ("2027-11-24", "October 2027"),
                  ("2027-12-22", "November 2027")]},
}

# ------------------------------------------------------------------ A13 Russell (halbjährlich ab 2026)
# FTSE Russell, Pressemitteilung 1.9.2026 (Dezember) und CME-Artikel (Juni 2026)
RUSSELL = {
    "2026-06": {"rank_day": "2026-04-30", "preliminary_lists": "2026-05-22",
                "effective_after_close": "2026-06-26",
                "source": "https://www.cmegroup.com/articles/2026/the-2026-russell-reconstitution.html"},
    "2026-12": {"rank_day": "2026-10-30", "preliminary_lists": "2026-11-13", "lockdown_start": "2026-11-30",
                "effective_after_close": "2026-12-11",
                "source": "https://www.lseg.com/en/media-centre/press-releases/ftse-russell/2026/"
                          "ftse-russell-announces-december-2026-russell-us-indexes-reconstitution-schedule"},
}
