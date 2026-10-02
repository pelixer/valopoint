"""Descriptive player profiles for the Players page (form, consistency, career,
regional-league season, current event). Not used for prediction.

Everything is on the PP scale (100 = average player) and built from the model's
per-map opponent-adjusted performance (`PlayerModel.rows.perf`): the same quantity
the power points are estimated from, so a player's numbers here are comparable
across leagues, events and roles. Averages over few rounds are shrunk toward the
player's own baseline so a hot week does not top a list on its own.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .model import pp

FORM_DAYS = 60          # "recent" window for form
K_FORM = 400.0          # rounds of prior weight when shrinking recent form (~18 maps)
K_INTL = 600.0          # rounds of prior weight for international vs league level
MIN_MAPS_STEADY = 20


def _short(name: str) -> str:
    s = re.sub(r"^(VCT \d{4}: |Valorant )", "", name or "")
    return s.replace("Champions Tour ", "")


def _wmean(x, w):
    w = np.asarray(w, float)
    return float(np.average(x, weights=w)) if w.sum() > 0 else float("nan")


def player_profiles(m, as_of, pkeys, base_theta: dict, current_event: int | None = None) -> dict:
    """pkey -> profile dict. `base_theta` = the player's exported PP in theta units."""
    rows = m.rows
    rows = rows[rows["pkey"].isin(pkeys)].copy()
    rows["ppv"] = pp(rows["perf"].to_numpy())
    rows["win"] = (rows["team_rounds"] > rows["opp_rounds"]).astype(int)
    as_of = pd.Timestamp(as_of)
    recent_cut = as_of - pd.Timedelta(days=FORM_DAYS)
    year_cut = as_of - pd.Timedelta(days=365)
    out = {}
    for pk, g in rows.groupby("pkey"):
        g = g.sort_values("date")
        base = float(pp(base_theta.get(pk, g["perf"].mean())))
        prof: dict = {}

        # ---- form: recent 60 days vs the 60-365 days before, both shrunk
        rec = g[g["date"] >= recent_cut]
        old = g[(g["date"] < recent_cut) & (g["date"] >= year_cut)]
        old_mean = _wmean(old["ppv"], old["R"]) if len(old) else base
        old_s = (old["R"].sum() * old_mean + K_FORM * base) / (old["R"].sum() + K_FORM)
        if len(rec):
            rec_s = (float((rec["R"] * rec["ppv"]).sum()) + K_FORM * old_s) / (rec["R"].sum() + K_FORM)
            prof["form"] = {"recent": round(rec_s, 1), "before": round(old_s, 1),
                            "delta": round(rec_s - old_s, 1), "maps": int(rec["game_id"].nunique())}

        # ---- consistency over the last year (map-to-map spread of performance)
        y = g[g["date"] >= year_cut]
        if y["game_id"].nunique() >= MIN_MAPS_STEADY:
            mu = _wmean(y["ppv"], y["R"])
            sd = float(np.sqrt(np.average((y["ppv"] - mu) ** 2, weights=y["R"])))
            prof["steady"] = {"sd": round(sd, 1), "floor": round(float(np.percentile(y["ppv"], 25)), 1),
                              "maps": int(y["game_id"].nunique())}

        # ---- career: international results over the data window (2 years)
        it = g[g["intl"]]
        lg = g[~g["intl"]]
        lg_mean = _wmean(lg["ppv"], lg["R"]) if len(lg) else base
        if len(it):
            raw = _wmean(it["ppv"], it["R"])
            shr = (it["R"].sum() * raw + K_INTL * lg_mean) / (it["R"].sum() + K_INTL)
            prof["intl"] = {"events": int(it["event_id"].nunique()), "maps": int(it["game_id"].nunique()),
                            "map_wins": int(it.drop_duplicates("game_id")["win"].sum()),
                            "pp": round(shr, 1), "pp_raw": round(raw, 1), "league_pp": round(lg_mean, 1),
                            "big_stage": round(shr - lg_mean, 1),
                            "list": [_short(n) for n in it.drop_duplicates("event_id")["event"]]}

        # ---- latest regional-league event the player played
        if len(lg):
            last_ev = lg["event_id"].iloc[-1]
            le = lg[lg["event_id"] == last_ev]
            mapsd = le.drop_duplicates("game_id")
            raw = _wmean(le["ppv"], le["R"])
            prof["league"] = {"event": _short(le["event"].iloc[0]), "maps": int(len(mapsd)),
                              "map_wins": int(mapsd["win"].sum()),
                              "pp": round((le["R"].sum() * raw + K_FORM * base) / (le["R"].sum() + K_FORM), 1),
                              "pp_raw": round(raw, 1)}

        # ---- the international event in progress
        if current_event is not None:
            ce = g[g["event_id"] == current_event]
            if len(ce):
                mapsd = ce.drop_duplicates("game_id")
                raw = _wmean(ce["ppv"], ce["R"])
                prof["current"] = {"maps": int(len(mapsd)), "map_wins": int(mapsd["win"].sum()),
                                   "pp": round((ce["R"].sum() * raw + K_FORM * base) / (ce["R"].sum() + K_FORM), 1),
                                   "pp_raw": round(raw, 1)}

        # ---- timeline: one point per event
        tl = []
        for eid, e in g.groupby("event_id", sort=False):
            tl.append([_short(e["event"].iloc[0]), str(e["date"].min().date()), int(e["game_id"].nunique()),
                       round(_wmean(e["ppv"], e["R"]), 1), bool(e["intl"].iloc[0]),
                       int(e.drop_duplicates("game_id")["win"].sum())])
        prof["timeline"] = sorted(tl, key=lambda x: x[1])
        out[pk] = prof
    return out
