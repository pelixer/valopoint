"""Build the JSON consumed by the web app (web/public/data/model.json)."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .agents import AGENT_ROLE, role_of
from .backtest import metrics, walk_forward
from .model import MAIN_REGIONS, Params, fit, pp
from .predict import fit_gamma, map_pool, rosters, team_region


def build(df: pd.DataFrame, params: Params | None = None, as_of=None, source: str = "vlr.gg",
          brackets_dir: str | Path | None = None, active_days: int = 150, log=print) -> dict:
    p = params or Params()
    as_of = pd.Timestamp(as_of) if as_of else df["date"].max() + pd.Timedelta(days=1)
    since = as_of - pd.Timedelta(days=p.window_days)

    log("walk-forward over international events (out-of-sample strength gaps)...")
    rec, _ = walk_forward(df[df["date"] < as_of], p, "live", since=since)
    beta, gamma = fit_gamma(rec, as_of, p.half_life_days, p.gamma_l2)
    live = set(df[(df["date"] >= as_of - pd.Timedelta(days=21)) & df["intl"]]["event_id"])
    m = fit(df, replace(p, beta=beta), as_of=as_of, live_events=live or None)
    m.gamma = gamma

    pool = map_pool(df, as_of)
    ros = rosters(df, as_of)
    reg = team_region(df)
    last = df.groupby("team")["date"].max()
    active = [t for t in ros if last[t] >= as_of - pd.Timedelta(days=active_days)
              and reg.get(t) in MAIN_REGIONS and len(ros[t]) == 5]

    teams = []
    # descriptive team context for match pages: per-map record (last 365 days) and recent maps
    from .dataset import games as _games
    gm = _games(df[(df["date"] < as_of) & (df["date"] >= as_of - pd.Timedelta(days=365))])
    all_maps = sorted(set(pool) | set(gm["map"].unique()))
    for t in active:
        by_map = {mp: m.team_strength(ros[t], mp, reg[t]) for mp in all_maps}
        tg = gm[gm["team"] == t].sort_values(["date", "match_id", "map_order"])
        map_rec = {mp: [int(len(x)), int(x["win"].sum()), int(x["team_rounds"].sum()), int((x["team_rounds"] + x["opp_rounds"]).sum())]
               for mp, x in tg.groupby("map")}
        recent = [[str(r.date.date()), r.opp, r.map, int(r.team_rounds), int(r.opp_rounds)]
                  for r in tg.tail(40).itertuples()]
        teams.append({"name": t, "region": reg[t], "roster": ros[t],
                      "theta": by_map, "pp": float(pp(sum(by_map[mp] for mp in pool) / len(pool) / 5) * 5),
                      "map_record": map_rec, "recent": recent})
    teams.sort(key=lambda x: -x["pp"])

    wanted = {pk for t in active for pk in ros[t]}
    players = {}
    pa = m.p_agent.set_index(["pkey", "agent"])
    pm = m.p_map.set_index(["pkey", "map"])
    mix = m.agent_mix
    for pk in wanted:
        if pk not in m.player.index:
            continue
        row = m.player.loc[pk]
        agents = pa.loc[pk] if pk in pa.index.get_level_values(0) else pd.DataFrame(columns=["dev", "rounds"])
        maps = pm.loc[pk] if pk in pm.index.get_level_values(0) else pd.DataFrame(columns=["dev", "rounds"])
        pmix = mix[mix["pkey"] == pk]
        main_agent = agents["rounds"].idxmax() if len(agents) else ""
        treg = next((reg[t] for t in active if pk in ros[t]), row["region"])
        base = m.region.get(treg, 0.0) + row["u"]
        grid = {}
        for mp in sorted(set(pool) | set(maps.index)):
            dm = float(maps.loc[mp, "dev"]) if mp in maps.index else 0.0
            grid[mp] = {a: round(float(pp(base + dm + agents.loc[a, "dev"])), 1) for a in agents.index}
        players[pk] = {
            "name": row["name"], "team": next((t for t in active if pk in ros[t]), row["team"]),
            "region": treg, "role": role_of(main_agent),
            "pp": round(float(pp(base)), 1), "rounds": int(row["rounds"]),
            "maps": {mp: {"pp": round(float(pp(base + maps.loc[mp, "dev"])), 1),
                          "rounds": int(maps.loc[mp, "rounds"])} for mp in maps.index},
            "agents": {a: {"pp": round(float(pp(base + agents.loc[a, "dev"])), 1),
                           "rounds": int(agents.loc[a, "rounds"])} for a in agents.index},
            "grid": grid,
            "mix": {str(mp): dict(zip(g["agent"], g["weight"].round(3)))
                    for mp, g in pmix.groupby(pmix["map"].fillna("*"))},
        }

    # play-style attributes (descriptive only; not used for prediction — see docs/style_test_*.md)
    from .styles import STYLE_AXES, style_percentiles
    styles = style_percentiles(df[df["date"] < as_of], as_of)
    for pk, pl in players.items():
        if pk in styles:
            pl["style"] = styles[pk]

    brackets = []
    if brackets_dir and Path(brackets_dir).exists():
        for f in sorted(Path(brackets_dir).glob("*.json")):
            brackets.append(json.loads(f.read_text(encoding="utf-8")))

    # accuracy check on the current international event (pre-event for each team's
    # first match, live afterwards)
    event_eval = None
    intl_now = df[df["intl"] & (df["date"] >= as_of - pd.Timedelta(days=60))]
    if not intl_now.empty:
        from .evaluate import evaluate_event
        eid = int(intl_now.sort_values("date")["event_id"].iloc[-1])
        log(f"evaluating event {eid}...")
        event_eval = evaluate_event(df[df["date"] < as_of], eid, p)
        event_eval["name"] = str(df.loc[df["event_id"] == eid, "event"].iloc[0])

    bt = metrics(rec)
    return {
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "as_of": str(as_of.date()), "source": source,
                 "data_from": str(since.date()), "params": p.to_dict(), "diag": m.diag,
                 "backtest_map": bt, "live_events": sorted(int(e) for e in live)},
        "calib": {"beta": beta},
        "regions": {r: {"offset_pp": round(float(m.region.get(r, 0.0) * 1000), 2),
                        "gamma": round(gamma.get(r, 0.0), 4)} for r in MAIN_REGIONS},
        "maps": pool,
        "roles": AGENT_ROLE,
        "teams": teams,
        "players": players,
        "style_axes": STYLE_AXES,
        "brackets": brackets,
        "event_eval": event_eval,
    }


def write(model_json: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model_json, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
