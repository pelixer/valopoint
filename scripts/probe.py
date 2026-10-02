"""Probe vlr.gg performance tab: every table after the kill matrices (multi-kills, clutches)."""
import re
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

from valopoint.scrape.vlr import Fetcher

f = Fetcher(delay=1.0, cache=Path(tempfile.mkdtemp()), max_seconds=30)
MID = 753455  # Champions 2026, Team Liquid vs Paper Rex (finished, 3 maps)


def sq(x, n):
    return re.sub(r"\s+", " ", str(x))[:n]


for tab in ["performance"]:
    html = f.get(f"/{MID}/?game=all&tab={tab}")
    s = BeautifulSoup(html, "html.parser")
    print(f"\n######## tab={tab}  size={len(html)}")
    games = s.select(".vm-stats-game")
    print("games:", [g.get("data-game-id") for g in games])
    g = next((g for g in games if g.get("data-game-id") not in (None, "all")), games[0] if games else None)
    if g is None:
        continue
    tables = g.select("table")
    print("tables:", [t.get("class") for t in tables])
    for t in tables[3:]:
        print("\n--- TABLE classes", t.get("class"))
        print(sq(t.select_one("tr"), 1500))
        rows = t.select("tr")
        print("rows:", len(rows), "| row2:", sq(rows[1] if len(rows) > 1 else "", 2500))
    if not g.select("table"):
        print(sq(g, 5000))

