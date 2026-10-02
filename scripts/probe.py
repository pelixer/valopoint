"""Probe vlr.gg match tabs: performance (multi-kills, clutches), economy, round-by-round rows."""
import re
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

from valopoint.scrape.vlr import Fetcher

f = Fetcher(delay=1.0, cache=Path(tempfile.mkdtemp()), max_seconds=30)
MID = 753455  # Champions 2026, Team Liquid vs Paper Rex (finished, 3 maps)


def sq(x, n):
    return re.sub(r"\s+", " ", str(x))[:n]


for tab in ["performance", "economy"]:
    html = f.get(f"/{MID}/?game=all&tab={tab}")
    s = BeautifulSoup(html, "html.parser")
    print(f"\n######## tab={tab}  size={len(html)}")
    games = s.select(".vm-stats-game")
    print("games:", [g.get("data-game-id") for g in games])
    g = next((g for g in games if g.get("data-game-id") not in (None, "all")), games[0] if games else None)
    if g is None:
        continue
    for t in g.select("table")[:3]:
        print("\n--- TABLE classes", t.get("class"))
        print(sq(t, 3500))
    if not g.select("table"):
        print(sq(g, 5000))

# round-by-round rows on the overview tab
s = BeautifulSoup(f.get(f"/{MID}"), "html.parser")
g = next(g for g in s.select(".vm-stats-game") if g.get("data-game-id") not in (None, "all"))
rr = g.select_one(".vlr-rounds")
print("\n######## overview rounds block")
print(sq(rr, 4000))
