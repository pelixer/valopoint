"""Dump vlr.gg event match-list and bracket page structure (for the bracket scraper)."""
import re
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

from valopoint.scrape.vlr import Fetcher

f = Fetcher(delay=1.0, cache=Path(tempfile.mkdtemp()), max_seconds=30)


def sq(x, n):
    return re.sub(r"\s+", " ", str(x))[:n]


html = f.get("/event/matches/2766/?series_id=all")
soup = BeautifulSoup(html, "html.parser")
items = soup.select("a.match-item, a.wf-module-item")
print("match list items:", len(items))
for a in items[:2] + items[-2:]:
    print("\n--- ITEM", a.get("href"), "\n", sq(a, 2500))
labels = soup.select(".wf-label.mod-large")
print("\ndate labels:", [sq(l.get_text(" ", strip=True), 60) for l in labels][:20])

ev = BeautifulSoup(f.get("/event/2766"), "html.parser")
print("\nEVENT TABS:", [(a.get("href"), sq(a.get_text(' ', strip=True), 40)) for a in ev.select("a.wf-subnav-item, .wf-nav a")][:20])
for path in ["/event/2766/valorant-champions-2026/group-stage", "/event/2766/valorant-champions-2026/playoffs"]:
    s = BeautifulSoup(f.get(path), "html.parser")
    print(f"\n######## {path}")
    for sel in [".bracket-container", ".bracket-row", ".bracket-col", ".bracket-item", ".bracket-item-team",
                ".bracket-item-team-name", ".bracket-col-label", ".event-groups-container", ".wf-table", ".group-table"]:
        print(f"  {sel:28s} {len(s.select(sel))}")
    cont = s.select_one(".bracket-container") or s.select_one(".event-groups-container") or s.select_one(".col.mod-1")
    print(sq(cont, 6000))
