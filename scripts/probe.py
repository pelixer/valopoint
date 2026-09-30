"""Dump the real structure around player stat cells on a vlr.gg match page."""
import re
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

from valopoint.scrape.vlr import Fetcher

f = Fetcher(delay=1.0, cache=Path(tempfile.mkdtemp()), max_seconds=30)
html = f.get("/753455")  # Champions 2026, Team Liquid vs Paper Rex (finished)


def squash(s, n):
    s = re.sub(r"\s+", " ", str(s))
    return s[:n]


print("raw '<table' occurrences:", html.count("<table"), " '<tr':", html.count("<tr"),
      " 'mod-player':", html.count("mod-player"), " 'mod-agents':", html.count("mod-agents"))
i = html.find("mod-both")
print("\nRAW around first mod-both:\n", squash(html[max(0, i - 3000): i + 600], 4000))

for parser in ("html.parser", "lxml"):
    try:
        soup = BeautifulSoup(html, parser)
    except Exception as e:
        print(parser, "unavailable:", e)
        continue
    print(f"\n==== parser={parser}: tables={len(soup.select('table'))} "
          f"td.mod-player={len(soup.select('td.mod-player'))} .mod-player={len(soup.select('.mod-player'))}")
    game = next(g for g in soup.select(".vm-stats-game") if g.get("data-game-id") not in (None, "all"))
    both = game.select_one(".mod-both")
    chain = []
    el = both
    while el is not None and el is not game:
        chain.append(f"{el.name}.{'.'.join(el.get('class') or [])}")
        el = el.parent
    print("ancestor chain of first .mod-both in game:", " < ".join(chain))
    # the element that looks like one player's row: nearest ancestor containing a player link
    row = both
    while row is not None and row.select_one("a[href^='/player/']") is None:
        row = row.parent
    print("\nPLAYER ROW:\n", squash(row, 5000))
    print("\nDIRECT CHILDREN OF GAME:", [f"{c.name}.{'.'.join(c.get('class') or [])}" for c in game.find_all(recursive=False)])
