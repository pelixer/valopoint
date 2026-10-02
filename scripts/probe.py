"""Probe: run the round / side / performance / economy parsers on a real match."""
import tempfile
from pathlib import Path

import pandas as pd

from valopoint.scrape.extras import scrape_match_extras
from valopoint.scrape.vlr import Fetcher

f = Fetcher(delay=1.0, cache=Path(tempfile.mkdtemp()), max_seconds=30)
pd.set_option("display.width", 250, "display.max_columns", 40)
for mid in (753455, 542275):   # Champions 2026 TL-PRX; an older 2025 match
    try:
        ex = scrape_match_extras(f, mid)
    except Exception as e:
        print(mid, "ERROR", e); continue
    print(f"\n######## match {mid}")
    for k, rows in ex.items():
        d = pd.DataFrame(rows)
        print(f"\n--- {k}: {len(d)} rows, null share:\n{d.isna().mean().round(2).to_dict() if len(d) else {}}")
        print(d.head(6).to_string() if len(d) else "(empty)")
    r = pd.DataFrame(ex["rounds"])
    if len(r):
        print("\nrounds per game / team:\n", r.groupby(["game_id", "winner", "win_side"]).size())
