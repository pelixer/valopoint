"""Validate the parser on real vlr.gg pages: one full finished event + a live one."""
import tempfile
import time
from collections import Counter
from pathlib import Path

import pandas as pd

from valopoint.scrape.vlr import Fetcher, scrape_event

f = Fetcher(delay=1.0, cache=Path(tempfile.mkdtemp()), max_seconds=30)
for eid in (2765, 2766):
    t0 = time.time()
    rows, complete = scrape_event(f, eid)
    df = pd.DataFrame(rows)
    print(f"\n######## event {eid}: {len(df)} rows, complete={complete}, {time.time() - t0:.0f}s")
    if df.empty:
        continue
    per_side = df.groupby(["game_id", "team"]).size()
    print("maps:", df["game_id"].nunique(), " players/side:", dict(Counter(per_side)))
    print("map names:", dict(Counter(df.drop_duplicates("game_id")["map"])))
    print("agents:", dict(Counter(df["agent"]).most_common(12)))
    print("null share per column:\n", df.isna().mean().round(3).to_string())
    print(df.head(12).to_string())
