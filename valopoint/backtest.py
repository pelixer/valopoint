"""Walk-forward evaluation on international events.

Modes
  live   : refit before every match day, including earlier days of the same event
           (weighted by Params.w_live)  -> "update during the event"
  frozen : one fit per event, before it starts -> "pre-tournament prediction only"
Comparing the two, and sweeping w_live / half_life / k_mult, is how the
"when and how much to trust in-event stats" question is answered empirically.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import replace

import numpy as np
import pandas as pd

from .dataset import games
from .model import Params, fit
from .predict import fit_gamma, map_pool, series_forecast, series_prob_ordered
from .rating import Match, Params as EloParams, RatingBook


def _eval_games(df: pd.DataFrame, since=None) -> pd.DataFrame:
    g = games(df)
    g = g[g["intl"] & (g["team"] < g["opp"])]
    if since is not None:
        g = g[g["date"] >= pd.Timestamp(since)]
    return g.sort_values(["date", "match_id", "map_order"])


def walk_forward(df: pd.DataFrame, params: Params | None = None, mode: str = "live",
                 since=None, series: bool = False, log=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = params or Params()
    ev = _eval_games(df, since)
    region_of = df.groupby("team")["team_region"].first().to_dict()
    lineup = df.groupby(["game_id", "team"])["pkey"].apply(list).to_dict()
    if mode == "frozen":
        start = ev.groupby("event_id")["date"].transform("min")
        ev = ev.assign(as_of=start)
    else:
        ev = ev.assign(as_of=ev["date"])

    recs, srecs = [], []
    for (as_of, eid), grp in ev.groupby(["as_of", "event_id"], sort=True):
        prior = pd.DataFrame(recs)
        if len(prior):
            prior = prior[(prior["event_id"] != eid) & (pd.to_datetime(prior["date"]) < as_of)]
        beta, gamma = fit_gamma(prior, as_of, p.half_life_days, p.gamma_l2) if len(prior) else (1.0, {})
        live = {eid} if mode == "live" else None
        try:
            m = fit(df, replace(p, beta=beta), as_of=as_of, live_events=live)
        except ValueError:
            continue
        m.gamma = gamma
        for r in grp.itertuples():
            ra, rb = lineup[(r.game_id, r.team)], lineup[(r.game_id, r.opp)]
            ga, gb = region_of[r.team], region_of[r.opp]
            dS = m.team_strength(ra, r.map, ga) - m.team_strength(rb, r.map, gb)
            recs.append(dict(date=r.date, event_id=eid, match_id=r.match_id, game_id=r.game_id,
                             map=r.map, best_of=r.best_of, team_a=r.team, team_b=r.opp,
                             region_a=ga, region_b=gb, intl=True, dS=dS,
                             p=float(m.calibrated(dS, ga, gb)),
                             win=r.win))
        if series:
            pool = map_pool(df, as_of)
            for mid, mg in grp.groupby("match_id"):
                r = mg.iloc[0]
                ra, rb = lineup[(r.game_id, r.team)], lineup[(r.game_id, r.opp)]
                f = series_forecast(m, ra, rb, region_of[r.team], region_of[r.opp], pool, int(r.best_of))
                won = mg["win"].sum() > (len(mg) - mg["win"].sum())
                srecs.append(dict(date=r.date, event_id=eid, match_id=mid, team_a=r.team, team_b=r.opp,
                                  p=f["series"], win=float(won)))
        if log:
            log(f"  {as_of.date()} event {eid}: {len(grp)} maps")
    return pd.DataFrame(recs), pd.DataFrame(srecs)


def elo_baseline(df: pd.DataFrame, since=None) -> pd.DataFrame:
    g = games(df).sort_values(["date", "match_id", "map_order"])
    g = g[g["team"] < g["opp"]]
    ev_ids = set(_eval_games(df, since)["game_id"])
    book = RatingBook(EloParams(k_team=16, margin_weight=0.5))
    region_of = df.groupby("team")["team_region"].first().to_dict()
    out = []
    for r in g.itertuples():
        ra, rb = region_of[r.team], region_of[r.opp]
        book._get(r.team, ra); book._get(r.opp, rb)
        if r.game_id in ev_ids:
            out.append(dict(game_id=r.game_id, p=book.map_win_prob(r.team, r.opp), win=r.win))
        book.update(Match(r.date.date(), str(r.event_id), "", r.team, r.opp, ra, rb,
                          int(r.win), int(1 - r.win), 1, int(r.team_rounds), int(r.opp_rounds)))
    return pd.DataFrame(out)


def metrics(rec: pd.DataFrame) -> dict:
    if rec is None or len(rec) == 0:
        return {"n": 0}
    p = rec["p"].clip(1e-6, 1 - 1e-6).to_numpy()
    y = rec["win"].to_numpy()
    return {"n": int(len(rec)),
            "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
            "brier": float(np.mean((p - y) ** 2)),
            "accuracy": float(np.mean((p > 0.5) == (y == 1)))}


def compare(df: pd.DataFrame, params: Params | None = None, since=None, log=None) -> dict:
    live, s_live = walk_forward(df, params, "live", since, series=True, log=log)
    frozen, s_frozen = walk_forward(df, params, "frozen", since, series=True, log=log)
    elo = elo_baseline(df, since)
    return {"map": {"live": metrics(live), "frozen": metrics(frozen), "elo": metrics(elo),
                    "coin": {"log_loss": math.log(2)}},
            "series": {"live": metrics(s_live), "frozen": metrics(s_frozen)}}


def tune(df: pd.DataFrame, grid: dict, since=None, base: Params | None = None, log=print) -> pd.DataFrame:
    base = base or Params()
    keys = list(grid)
    rows = []
    for vals in itertools.product(*grid.values()):
        p = replace(base, **dict(zip(keys, vals)))
        rec, _ = walk_forward(df, p, "live", since)
        m = metrics(rec)
        rows.append({**dict(zip(keys, vals)), **m})
        if log:
            log(f"  {dict(zip(keys, vals))} -> logloss {m.get('log_loss', float('nan')):.4f}")
    return pd.DataFrame(rows).sort_values("log_loss")
