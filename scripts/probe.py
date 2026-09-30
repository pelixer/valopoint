"""Fetch a few real vlr.gg pages with the project Fetcher and run the parsers."""
import json
import tempfile
from pathlib import Path

from valopoint.scrape.events import discover
from valopoint.scrape.vlr import Fetcher, event_match_ids, parse_match

f = Fetcher(delay=1.0, cache=Path(tempfile.mkdtemp()), max_seconds=30)

ev = discover(f, [2026])
print(f"discover(2026): {len(ev)} events")
for e in ev[:40]:
    print("  ", e)

ids = event_match_ids(f, 2766)
print(f"event 2766 match ids: {len(ids)} {ids[:10]}")
for mid in ids[:3]:
    rows = parse_match(f.get(f"/{mid}"), mid, 2766, "Champions 2026")
    print(f"match {mid}: {len(rows)} rows")
    for r in rows[:3]:
        print("   ", json.dumps(r.__dict__, default=str, ensure_ascii=False))
