"""Discover VCT events from vlr.gg season hub pages and classify them.

Output (data/events.json) is meant to be reviewed/edited by hand:
  [{"event_id": 2766, "name": "Valorant Champions 2026", "region": "INTL",
    "tier": "champions", "year": 2026}, ...]
region: AMER | EMEA | PAC | CN | INTL
tier:   league (kickoff/stage/regular season) | qualifier | masters | champions
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .vlr import Fetcher

REGION_KEYS = [
    ("AMER", ["americas"]),
    ("EMEA", ["emea"]),
    ("PAC", ["pacific"]),
    ("CN", ["china"]),
]


def classify(name: str) -> tuple[str, str]:
    n = name.lower()
    if "champions" in n and "tour" not in n:
        return "INTL", "champions"
    if "masters" in n:
        return "INTL", "masters"
    region = next((r for r, keys in REGION_KEYS if any(k in n for k in keys)), "")
    tier = "qualifier" if ("qualifier" in n or "last chance" in n) else "league"
    return region, tier


def discover(f: Fetcher, years: list[int]) -> list[dict]:
    out, seen = [], set()
    for y in years:
        html = f.get(f"/vct-{y}", refresh=True)
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href^='/event/']"):
            m = re.match(r"^/event/(\d+)/", a.get("href", ""))
            if not m:
                continue
            eid = int(m.group(1))
            if eid in seen:
                continue
            title = a.select_one(".event-item-title, .wf-title-med, .text-of")
            name = (title or a).get_text(" ", strip=True)
            region, tier = classify(name)
            if not region:
                continue  # Game Changers, Challengers, showmatches etc.
            if "game changers" in name.lower() or "challengers" in name.lower():
                continue
            seen.add(eid)
            out.append({"event_id": eid, "name": name, "region": region, "tier": tier, "year": y})
    return out
