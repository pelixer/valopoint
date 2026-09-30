"""Dump the real structure of vlr.gg match pages so the parser can be fitted to it."""
import re
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

from valopoint.scrape.vlr import Fetcher, event_match_ids, parse_match

f = Fetcher(delay=1.0, cache=Path(tempfile.mkdtemp()), max_seconds=30)


def show(label, el, n=1500):
    html = str(el) if el is not None else "None"
    html = re.sub(r"\s+", " ", html)
    print(f"--- {label} ({len(html)} chars)\n{html[:n]}\n")


# a finished international event (Masters London 2026) and Champions 2026
for eid in (2765, 2766):
    ids = event_match_ids(f, eid)
    print(f"\n######## event {eid}: {len(ids)} matches, first {ids[:5]}, last {ids[-3:]}")
    mid = ids[-1]  # usually earliest listed last? print both ends
    for mid in (ids[0], ids[-1]):
        html = f.get(f"/{mid}")
        soup = BeautifulSoup(html, "html.parser")
        print(f"\n==== match {mid}  rows={len(parse_match(html, mid, eid, 'x'))}")
        for sel in [".match-header", ".match-header-link-name", ".wf-title-med", ".match-header-vs-note",
                    ".match-header-event-series", ".moment-tz-convert", ".vm-stats", ".vm-stats-game",
                    ".vm-stats-game-header", "table", "table.wf-table-inset", "table.mod-overview",
                    "td.mod-player", "td.mod-agents", "td.mod-stat", ".mod-both", ".score", ".map"]:
            print(f"  {sel:32s} {len(soup.select(sel))}")
        show("match-header", soup.select_one(".match-header"), 2500)
        games = soup.select(".vm-stats-game")
        print("  game ids:", [g.get("data-game-id") for g in games])
        g = next((g for g in games if g.get("data-game-id") not in (None, "all")), games[0] if games else None)
        if g is not None:
            show("game header", g.select_one(".vm-stats-game-header"), 2500)
            t = g.select_one("table")
            show("table attrs+thead", t.select_one("thead") if t else None, 1500)
            if t:
                print("  table classes:", t.get("class"))
            show("first player row", g.select_one("tbody tr"), 4000)
    if eid == 2765:
        continue
