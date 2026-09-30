from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main(argv=None):
    ap = argparse.ArgumentParser(prog="valopoint")
    ap.add_argument("--data", default="data", help="data dir with events.json and rows/")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("events", help="discover VCT events from vlr.gg into events.json")
    s.add_argument("--years", type=int, nargs="+", default=[2025, 2026])

    s = sub.add_parser("scrape", help="scrape events listed in events.json")
    s.add_argument("--event", type=int, nargs="*", help="only these event ids")
    s.add_argument("--delay", type=float, default=1.5)
    s.add_argument("--force", action="store_true", help="re-scrape events already stored")

    s = sub.add_parser("synth", help="write a synthetic dataset (for testing)")
    s.add_argument("out")

    s = sub.add_parser("players", help="player power points")
    s.add_argument("--top", type=int, default=25)
    s.add_argument("--map"); s.add_argument("--agent")

    sub.add_parser("backtest", help="walk-forward: live vs frozen vs Elo")

    s = sub.add_parser("tune", help="grid search Params on international maps")
    s.add_argument("--grid", default='{"w_live":[1,2,4],"half_life_days":[90,180,365]}')

    s = sub.add_parser("export", help="build web/public/data/model.json")
    s.add_argument("--out", default="web/public/data/model.json")
    s.add_argument("--source", default="vlr.gg")
    s.add_argument("--as-of")

    a = ap.parse_args(argv)
    data = Path(a.data)

    if a.cmd == "events":
        from .scrape.events import discover
        from .scrape.vlr import Fetcher
        ev = discover(Fetcher(), a.years)
        data.mkdir(exist_ok=True)
        (data / "events.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
        for e in ev:
            print(e)
        return
    if a.cmd == "scrape":
        from .scrape.vlr import Fetcher, scrape_event
        f = Fetcher(delay=a.delay)
        ev = json.loads((data / "events.json").read_text(encoding="utf-8"))
        (data / "rows").mkdir(parents=True, exist_ok=True)
        total = 0
        for e in ev:
            if a.event and e["event_id"] not in a.event:
                continue
            out = data / "rows" / f"{e['event_id']}.csv"
            if out.exists() and not a.force and e.get("complete"):
                continue
            print(f"event {e['event_id']} {e['name']}")
            rows, complete = scrape_event(f, e["event_id"])
            total += len(rows)
            if rows:
                pd.DataFrame(rows).to_csv(out, index=False)
            e["complete"] = complete
            (data / "events.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"scraped {total} player-map rows")
        return
    if a.cmd == "synth":
        from .synth import generate
        generate(a.out)
        print("wrote synthetic dataset to", a.out)
        return

    from .dataset import load
    df = load(data)

    if a.cmd == "players":
        from .model import fit, pp
        m = fit(df)
        pl = m.player.copy()
        pl["pp"] = [m.theta(k, a.map, a.agent) for k in pl.index]
        pl["pp"] = pp(pl["pp"])
        pl = pl[pl["rounds"] >= 200].sort_values("pp", ascending=False).head(a.top)
        print(pl[["name", "team", "region", "rounds", "pp"]].round(1).to_string())
        print("\nregion offsets (PP/player):", {k: round(v * 1000, 1) for k, v in m.region.items()})
        print("learned stat weights:", {k: round(v, 5) for k, v in m.diag["weights"].items()})
    elif a.cmd == "backtest":
        from .backtest import compare
        print(json.dumps(compare(df, log=print), indent=1))
    elif a.cmd == "tune":
        from .backtest import tune
        print(tune(df, json.loads(a.grid)).to_string())
    elif a.cmd == "export":
        from .export import build, write
        mj = build(df, as_of=a.as_of, source=a.source, brackets_dir=data / "brackets")
        write(mj, a.out)
        print(f"wrote {a.out}: {len(mj['teams'])} teams, {len(mj['players'])} players")


if __name__ == "__main__":
    main()
