"""Event-level accuracy check: how well did the model call an international event?

Rule (per team):
  * a team's FIRST match of the event is predicted with a model fitted only on
    data from before the event started (regional leagues + earlier events);
  * from its SECOND match on, the model is refitted before each match day and
    includes the event's earlier results, weighted by Params.w_live.

Predictions are genuinely pre-match: the actual lineup is used (known at match
time) but the maps are predicted with the veto model, so the series probability
is what the app would have shown before the match.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .backtest import elo_baseline, metrics, walk_forward
from .dataset import games
from .model import Params, fit
from .predict import fit_gamma, map_pool, series_forecast, series_prob_ordered


def event_matches(df: pd.DataFrame, event_id: int) -> pd.DataFrame:
    g = games(df[df["event_id"] == event_id])
    stage = df.groupby("match_id")["stage"].first()
    rows = []
    for mid, mg in g.groupby("match_id"):
        a, b = sorted(mg["team"].unique())
        wa = int(mg[(mg["team"] == a)]["win"].sum())
        wb = int(mg[(mg["team"] == b)]["win"].sum())
        bo = int(mg["best_of"].iloc[0])
        if max(wa, wb) < bo // 2 + 1:
            continue  # series still in progress
        rows.append(dict(match_id=mid, date=mg["date"].min(), team_a=a, team_b=b,
                         maps_a=wa, maps_b=wb, best_of=bo,
                         stage=stage.get(mid, ""), win=float(wa > wb),
                         games=mg[mg["team"] == a].sort_values("map_order")[["game_id", "map", "win"]].values.tolist()))
    return pd.DataFrame(rows).sort_values(["date", "match_id"]).reset_index(drop=True)


def evaluate_event(df: pd.DataFrame, event_id: int, params: Params | None = None) -> dict:
    p = params or Params()
    em = event_matches(df, event_id)
    if em.empty:
        return {"event_id": event_id, "matches": [], "summary": {}}
    start = em["date"].min()
    region_of = df.groupby("team")["team_region"].first().to_dict()
    lineup = df.groupby(["game_id", "team"])["pkey"].apply(list).to_dict()

    # calibration (beta, region gamma) from out-of-sample predictions of earlier events only
    prior, _ = walk_forward(df[df["date"] < start], p, "live",
                            since=start - pd.Timedelta(days=p.window_days))
    beta, gamma = fit_gamma(prior, start, p.half_life_days, p.gamma_l2)
    pp = replace(p, beta=beta)

    def calibrated(m):
        m.gamma = gamma
        return m

    frozen = calibrated(fit(df, pp, as_of=start))
    live_cache: dict = {}

    def live_model(d):
        if d not in live_cache:
            live_cache[d] = calibrated(fit(df, pp, as_of=d, live_events={event_id}))
        return live_cache[d]

    seen: set = set()
    out = []
    for r in em.itertuples():
        first_a, first_b = r.team_a not in seen, r.team_b not in seen
        ma = frozen if first_a else live_model(r.date)
        mb = frozen if first_b else live_model(r.date)
        g0 = r.games[0][0]
        ra, rb = lineup[(g0, r.team_a)], lineup[(g0, r.team_b)]
        rega, regb = region_of.get(r.team_a, "UNK"), region_of.get(r.team_b, "UNK")
        pool = map_pool(df, r.date)
        # per-map strength from each team's own model, combined on the shared scale
        pmap = {}
        for mp in pool:
            dS = ma.team_strength(ra, mp, rega) - mb.team_strength(rb, mp, regb)
            pmap[mp] = float(frozen.calibrated(dS, rega, regb))
        from .predict import veto_maps
        ps = [series_prob_ordered([pmap[x] for x in veto_maps(pmap, r.best_of, af)]) for af in (True, False)]
        p_series = float(np.mean(ps))
        # map-level, on the maps actually played
        map_recs = []
        for gid, mp, w in r.games:
            dS = ma.team_strength(ra, mp, rega) - mb.team_strength(rb, mp, regb)
            map_recs.append(dict(map=mp, p=float(frozen.calibrated(dS, rega, regb)), win=float(w)))
        out.append(dict(match_id=int(r.match_id), date=str(r.date.date()), stage=r.stage,
                        team_a=r.team_a, team_b=r.team_b, score=f"{r.maps_a}-{r.maps_b}",
                        basis_a="pre-event" if first_a else "live", basis_b="pre-event" if first_b else "live",
                        p=p_series, win=r.win, correct=bool((p_series > 0.5) == (r.win == 1.0)),
                        maps=map_recs))
        seen.update([r.team_a, r.team_b])

    res = pd.DataFrame(out)
    maps = pd.DataFrame([m for o in out for m in o["maps"]])
    first = res[(res["basis_a"] == "pre-event") | (res["basis_b"] == "pre-event")]
    later = res[(res["basis_a"] == "live") & (res["basis_b"] == "live")]
    # Elo baseline on the same maps (series via the maps actually played)
    elo = elo_baseline(df, since=start)
    elo = elo[elo["game_id"].isin([g[0] for o in em["games"] for g in o])]
    return {
        "event_id": event_id,
        "params": {"w_live": p.w_live, "half_life_days": p.half_life_days, "beta": beta},
        "summary": {
            "series_all": metrics(res), "series_first_match": metrics(first),
            "series_later": metrics(later), "maps": metrics(maps), "maps_elo": metrics(elo),
        },
        "matches": out,
    }
