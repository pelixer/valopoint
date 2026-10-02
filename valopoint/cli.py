from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main(argv=None):
    ap = argparse.ArgumentParser(prog="valopoint")
    ap.add_argument("--data", default="data", help="data dir with events.json and rows/")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("events", help="discover VCT events from vlr.gg and merge into events.json")
    s.add_argument("--years", type=int, nargs="+", help="default: last year and this year")

    s = sub.add_parser("bracket", help="scrape the most relevant ongoing event's bracket")
    s.add_argument("--event", type=int, help="force a specific event id")
    s.add_argument("--out", default="web/public/data/brackets.json")

    s = sub.add_parser("scrape", help="scrape events listed in events.json")
    s.add_argument("--event", type=int, nargs="*", help="only these event ids")
    s.add_argument("--delay", type=float, default=1.5)
    s.add_argument("--force", action="store_true", help="re-scrape events already stored")

    s = sub.add_parser("veto", help="backfill map vetoes for recent finished events (uses the page cache)")
    s.add_argument("--periods", type=int, default=3, help="how many most recent event periods to cover")

    s = sub.add_parser("extras", help="round / side / clutch / multi-kill / economy data per finished match")
    s.add_argument("--event", type=int, nargs="*", help="only these event ids")
    s.add_argument("--max-minutes", type=float, default=60.0, help="stop after this long (resumes next run)")

    s = sub.add_parser("ledger", help="append pre-match predictions to the append-only ledger")
    s.add_argument("--model", default="web/public/data/model.json")
    s.add_argument("--brackets", default="web/public/data/brackets.json")
    s.add_argument("--out", default="web/public/data/ledger.json")

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
        from datetime import date
        from .scrape.events import discover
        from .scrape.vlr import Fetcher
        years = a.years or [date.today().year - 1, date.today().year]
        found = discover(Fetcher(), years)
        path = data / "events.json"
        old = {e["event_id"]: e for e in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}
        merged = {**{e["event_id"]: e for e in found}}
        for eid, e in old.items():          # keep completion flags and hand edits
            merged[eid] = {**merged.get(eid, {}), **e}
        ev = sorted(merged.values(), key=lambda e: -e["event_id"])
        data.mkdir(exist_ok=True)
        path.write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{len(ev)} events ({len(set(merged) - set(old))} new)")
        return
    if a.cmd == "bracket":
        from datetime import datetime, timezone
        from pathlib import Path as P
        from .scrape.bracket import pick_event, scrape_bracket
        from .scrape.vlr import Fetcher
        ev = json.loads((data / "events.json").read_text(encoding="utf-8"))
        target = next((e for e in ev if e["event_id"] == a.event), None) if a.event else pick_event(ev)
        if target is None:
            print("no event"); return
        br = scrape_bracket(Fetcher(delay=1.0), target)
        out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "brackets": [br]}
        P(a.out).parent.mkdir(parents=True, exist_ok=True)
        P(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{target['name']}: {len(br['matches'])} matches, {len(br['results'])} played, kind={br['kind']}")
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
            vetoes: list = []
            rows, complete = scrape_event(f, e["event_id"], name=e["name"], vetoes=vetoes)
            total += len(rows)
            if rows:
                pd.DataFrame(rows).to_csv(out, index=False)
            if vetoes:
                (data / "veto").mkdir(parents=True, exist_ok=True)
                (data / "veto" / f"{e['event_id']}.json").write_text(json.dumps(vetoes, ensure_ascii=False), encoding="utf-8")
            e["complete"] = complete
            (data / "events.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"scraped {total} player-map rows")
        return
    if a.cmd == "veto":
        from .scrape.vlr import Fetcher, event_match_ids, parse_match_veto
        from .veto import recent_periods
        ev = json.loads((data / "events.json").read_text(encoding="utf-8"))
        rows = pd.concat([pd.read_csv(p, usecols=["event_id", "date"]) for p in (data / "rows").glob("*.csv")])
        starts = rows.groupby("event_id")["date"].min().to_dict()
        target = [eid for per in recent_periods(ev, starts, a.periods + 1) for eid in per]
        f = Fetcher(delay=1.0)
        (data / "veto").mkdir(parents=True, exist_ok=True)
        for eid in target:
            out = data / "veto" / f"{eid}.json"
            if out.exists():
                continue
            vs = []
            for mid in event_match_ids(f, eid):
                try:
                    v = parse_match_veto(f.get(f"/{mid}"), mid, eid)
                except Exception as e:
                    print(f"  match {mid}: {e}"); continue
                if v:
                    vs.append(v)
            out.write_text(json.dumps(vs, ensure_ascii=False), encoding="utf-8")
            print(f"event {eid}: {len(vs)} vetoes")
        return
    if a.cmd == "extras":
        import time
        from .scrape.extras import scrape_match_extras
        from .scrape.vlr import Fetcher
        f = Fetcher(delay=1.0)
        t_end = time.time() + a.max_minutes * 60
        ev_dates = {int(p.stem): pd.read_csv(p, usecols=["date"])["date"].max() for p in (data / "rows").glob("*.csv")}
        done_all = True
        for eid in sorted(ev_dates, key=lambda e: ev_dates[e], reverse=True):   # newest events first
            if a.event and eid not in a.event:
                continue
            rows = pd.read_csv(data / "rows" / f"{eid}.csv", usecols=["match_id", "completed"])
            mids = sorted(rows.loc[rows["completed"].astype(bool), "match_id"].unique())
            outs = {k: data / k / f"{eid}.csv" for k in ("rounds", "sides", "adv", "econ")}
            old = {k: pd.read_csv(p) if p.exists() else pd.DataFrame() for k, p in outs.items()}
            have = set(old["sides"]["match_id"]) if "match_id" in old["sides"] else set()
            todo = [m for m in mids if m not in have]
            if not todo:
                continue
            print(f"event {eid}: {len(todo)} matches")
            new = {k: [] for k in outs}
            for mid in todo:
                if time.time() > t_end:
                    done_all = False
                    break
                try:
                    ex = scrape_match_extras(f, int(mid))
                except Exception as e:
                    print(f"  match {mid}: {e}"); continue
                for k in outs:
                    new[k].extend(ex[k])
            for k, p in outs.items():
                if new[k]:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    pd.concat([old[k], pd.DataFrame(new[k])], ignore_index=True).to_csv(p, index=False)
            print(f"  +{len(new['sides'])} player-maps, +{len(new['rounds'])} rounds, +{len(new['adv'])} adv, +{len(new['econ'])} econ")
            if not done_all:
                print("time budget reached; resumes next run")
                break
        return
    if a.cmd == "ledger":
        from .ledger import update
        n = update(a.model, a.brackets, a.out)
        print(f"ledger: {n} new snapshot(s)")
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
        mj = build(df, as_of=a.as_of, source=a.source, brackets_dir=data / "brackets", data_dir=data)
        write(mj, a.out)
        print(f"wrote {a.out}: {len(mj['teams'])} teams, {len(mj['players'])} players")


if __name__ == "__main__":
    main()
