"""Synthetic VCT-like dataset (NOT real data) with known hidden truth.

Used to verify that the model recovers region offsets, player strength and
player×map / player×agent effects, and to exercise the whole pipeline while
vlr.gg is unreachable.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .agents import ROLES

REGION_TRUE = {"AMER": 0.004, "EMEA": 0.006, "PAC": 0.002, "CN": -0.012}
MAPS_Y = {2025: ["ascent", "bind", "haven", "icebox", "lotus", "split", "sunset"],
          2026: ["ascent", "bind", "haven", "corrode", "lotus", "split", "abyss"]}
ROLE_ORDER = ["duelist", "initiator", "controller", "sentinel", "initiator"]
# role baselines for per-round stats: kpr dpr apr fkpr fdpr adr kast
ROLE_BASE = {
    "duelist":    [0.85, 0.72, 0.20, 0.16, 0.13, 150, 0.70],
    "initiator":  [0.70, 0.66, 0.40, 0.08, 0.07, 130, 0.74],
    "controller": [0.66, 0.66, 0.36, 0.06, 0.06, 122, 0.74],
    "sentinel":   [0.70, 0.64, 0.26, 0.07, 0.08, 125, 0.73],
}
LOAD = np.array([0.10, -0.08, 0.05, 0.03, -0.025, 18, 0.05])   # per unit performance z
NOISE = np.array([0.10, 0.08, 0.07, 0.04, 0.035, 16, 0.06])


def generate(out_dir: str | Path, seed: int = 7) -> dict:
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    out = Path(out_dir)
    (out / "rows").mkdir(parents=True, exist_ok=True)
    all_maps = sorted(set(sum(MAPS_Y.values(), [])))

    truth = {"region": REGION_TRUE, "player": {}, "player_map": {}, "player_agent": {}}
    teams = {}
    pid = 1000
    for reg in REGION_TRUE:
        for t in range(10):
            name = f"{reg}-{chr(65 + t)}"
            team_level = nrng.normal(0, 0.006)
            players = []
            for slot, role in enumerate(ROLE_ORDER):
                pid += 1
                agents = rng.sample(ROLES[role][:6], 2)
                u = team_level + nrng.normal(0, 0.006)
                pa = {a: nrng.normal(0, 0.004) for a in agents}
                pm = {m: nrng.normal(0, 0.003) for m in all_maps}
                players.append(dict(pid=pid, name=f"{name}.{slot}", role=role, agents=agents, u=u, pa=pa, pm=pm))
                truth["player"][str(pid)] = u + REGION_TRUE[reg]
                for m, v in pm.items():
                    truth["player_map"][f"{pid}|{m}"] = v
                for a, v in pa.items():
                    truth["player_agent"][f"{pid}|{a}"] = v
            teams[name] = dict(region=reg, players=players)

    events, rows = [], []
    eid = [5000]
    mid = [100000]

    def theta(p, reg, m, a):
        return REGION_TRUE[reg] + p["u"] + p["pm"][m] + p["pa"][a]

    def play_map(d, ev, ta, tb, m, order, bo, match_id):
        A, B = teams[ta], teams[tb]
        ag_a = [rng.choice(p["agents"]) for p in A["players"]]
        ag_b = [rng.choice(p["agents"]) for p in B["players"]]
        th_a = [theta(p, A["region"], m, a) for p, a in zip(A["players"], ag_a)]
        th_b = [theta(p, B["region"], m, a) for p, a in zip(B["players"], ag_b)]
        q = 0.5 + sum(th_a) - sum(th_b)
        wa = wb = 0
        while True:
            if rng.random() < q: wa += 1
            else: wb += 1
            if (wa >= 13 or wb >= 13) and abs(wa - wb) >= 2:
                break
        R = wa + wb
        share = wa / R
        gid = f"{match_id}-{order}"
        for side, (T, ags, ths, opp_ths, tr, orr, tname, oname) in enumerate([
                (A, ag_a, th_a, th_b, wa, wb, ta, tb), (B, ag_b, th_b, th_a, wb, wa, tb, ta)]):
            sh = share if side == 0 else 1 - share
            for p, a, th in zip(T["players"], ags, ths):
                z = (th - sum(opp_ths) / 5) / 0.01 + 4 * (sh - 0.5) + nrng.normal(0, 0.5)
                base = np.array(ROLE_BASE[p["role"]])
                s = base + LOAD * z + nrng.normal(0, 1, 7) * NOISE / np.sqrt(R / 24)
                s[:5] = np.clip(s[:5], 0, None); s[6] = np.clip(s[6], 0.2, 1.0)
                rows.append(dict(
                    match_id=match_id, game_id=gid, event_id=ev["event_id"], event=ev["name"],
                    stage="", date=d.isoformat(), map=m, map_order=order, team=tname, opp=oname,
                    team_rounds=tr, opp_rounds=orr, player=p["name"], player_id=p["pid"], agent=a,
                    rating=None, acs=None, k=round(s[0] * R), d=round(s[1] * R), a=round(s[2] * R),
                    kast=round(s[6] * 100), adr=round(s[5]), hs=None,
                    fk=round(s[3] * R), fd=round(s[4] * R), best_of=bo, completed=True))
        return wa > wb

    def play_series(d, ev, ta, tb, bo, pool):
        mid[0] += 1
        maps = rng.sample(pool, bo)
        need, wa, wb = bo // 2 + 1, 0, 0
        for i, m in enumerate(maps, 1):
            if play_map(d, ev, ta, tb, m, i, bo, mid[0]): wa += 1
            else: wb += 1
            if wa == need or wb == need:
                break
        return (ta, tb) if wa > wb else (tb, ta)

    def new_event(name, region, tier, year):
        eid[0] += 1
        e = {"event_id": eid[0], "name": name, "region": region, "tier": tier, "year": year}
        events.append(e)
        return e

    def league(d, year, label):
        for reg in REGION_TRUE:
            ev = new_event(f"VCT {year} {reg} {label}", reg, "league", year)
            names = [t for t in teams if teams[t]["region"] == reg]
            dd = d
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    if rng.random() < 0.5:
                        play_series(dd, ev, names[i], names[j], 3, MAPS_Y[year])
                        dd += timedelta(days=rng.randint(0, 1))
        return d + timedelta(days=35)

    def qualifiers(n):
        out = []
        for reg in REGION_TRUE:
            names = [t for t in teams if teams[t]["region"] == reg]
            strength = {t: sum(p["u"] for p in teams[t]["players"]) + nrng.normal(0, 0.02) for t in names}
            out += sorted(names, key=lambda t: -strength[t])[:n]
        return out

    def international(d, year, name, tier, per_region):
        ev = new_event(f"{name} {year}", "INTL", tier, year)
        alive = qualifiers(per_region)
        rng.shuffle(alive)
        dd = d
        # swiss-ish rounds then single elimination among survivors
        for _ in range(3):
            rng.shuffle(alive)
            for i in range(0, len(alive) - 1, 2):
                play_series(dd, ev, alive[i], alive[i + 1], 3, MAPS_Y[year])
            dd += timedelta(days=1)
        while len(alive) > 1:
            nxt = []
            for i in range(0, len(alive) - 1, 2):
                w, _ = play_series(dd, ev, alive[i], alive[i + 1], 5 if len(alive) == 2 else 3, MAPS_Y[year])
                nxt.append(w)
            alive = nxt
            dd += timedelta(days=1)
        return dd + timedelta(days=14)

    d = date(2024, 10, 1)
    for year in (2025, 2026):
        d = max(d, date(year, 1, 15))
        d = league(d, year, "Kickoff")
        d = international(d, year, "Masters Spring", "masters", 3)
        d = league(d, year, "Stage 1")
        d = international(d, year, "Masters Summer", "masters", 3)
        d = league(d, year, "Stage 2")
        d = international(d, year, "Champions", "champions", 4)

    df = pd.DataFrame(rows)
    for e in events:
        df[df["event_id"] == e["event_id"]].to_csv(out / "rows" / f"{e['event_id']}.csv", index=False)
    (out / "events.json").write_text(json.dumps(events, indent=1), encoding="utf-8")
    (out / "truth.json").write_text(json.dumps(truth), encoding="utf-8")

    # demo bracket: 8-team double elimination with the two best teams per region
    strength = {t: sum(p["u"] for p in v["players"]) for t, v in teams.items()}
    seeds = []
    for reg in REGION_TRUE:
        seeds += sorted([t for t in teams if teams[t]["region"] == reg], key=lambda t: -strength[t])[:2]
    seeds = seeds[0::2] + seeds[1::2]
    (out / "brackets").mkdir(exist_ok=True)
    demo = dict(DOUBLE_ELIM_8, id="demo", name="데모: 8팀 더블 엘리미네이션 (합성 데이터)", teams=seeds, results={})
    (out / "brackets" / "demo.json").write_text(json.dumps(demo, ensure_ascii=False, indent=1), encoding="utf-8")
    return truth


DOUBLE_ELIM_8 = {
    "matches": [
        {"id": "UB-QF1", "a": "S1", "b": "S8", "best_of": 3, "round": "상위 8강"},
        {"id": "UB-QF2", "a": "S4", "b": "S5", "best_of": 3, "round": "상위 8강"},
        {"id": "UB-QF3", "a": "S2", "b": "S7", "best_of": 3, "round": "상위 8강"},
        {"id": "UB-QF4", "a": "S3", "b": "S6", "best_of": 3, "round": "상위 8강"},
        {"id": "LB-R1A", "a": "L:UB-QF1", "b": "L:UB-QF2", "best_of": 3, "round": "하위 1R"},
        {"id": "LB-R1B", "a": "L:UB-QF3", "b": "L:UB-QF4", "best_of": 3, "round": "하위 1R"},
        {"id": "UB-SF1", "a": "W:UB-QF1", "b": "W:UB-QF2", "best_of": 3, "round": "상위 4강"},
        {"id": "UB-SF2", "a": "W:UB-QF3", "b": "W:UB-QF4", "best_of": 3, "round": "상위 4강"},
        {"id": "LB-R2A", "a": "W:LB-R1A", "b": "L:UB-SF2", "best_of": 3, "round": "하위 2R"},
        {"id": "LB-R2B", "a": "W:LB-R1B", "b": "L:UB-SF1", "best_of": 3, "round": "하위 2R"},
        {"id": "UB-F", "a": "W:UB-SF1", "b": "W:UB-SF2", "best_of": 3, "round": "상위 결승"},
        {"id": "LB-SF", "a": "W:LB-R2A", "b": "W:LB-R2B", "best_of": 3, "round": "하위 4강"},
        {"id": "LB-F", "a": "L:UB-F", "b": "W:LB-SF", "best_of": 5, "round": "하위 결승"},
        {"id": "GF", "a": "W:UB-F", "b": "W:LB-F", "best_of": 5, "round": "결승"},
    ],
    "final": "GF",
}
