"""Player play-style attributes (EXPERIMENTAL).

Beyond "how good" (PP), describe "how" a player plays, from per-map stats only.
Every axis is relative to the player's ROLE (duelists are compared with
duelists), so a style is not just a restatement of the agent pool.

Candidate axes
  entry       first-duel involvement   (FK+FD)/round
  entry_eff   first-duel win share     FK/(FK+FD), shrunk
  support     assists per round
  survival    -deaths per round
  firepower   damage per round
  aim         headshot %
  volatility  map-to-map swing of overall impact beyond sampling noise
  pressure    impact in close maps (margin <= 3 or OT) minus other maps
  decider     impact on deciding maps (map 3 / map 5) minus other maps
  bounce      impact after the team lost the previous map minus after a win

`reliability()` checks whether an axis is a stable trait (split-half test);
axes that do not replicate are noise and must not be used.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .model import learn_weights, standardize

AXES = ["entry", "entry_eff", "support", "survival", "firepower", "aim",
        "volatility", "pressure", "decider", "bounce"]


def map_level(df: pd.DataFrame) -> pd.DataFrame:
    """Per (player, map) row with role-relative per-round stats and context flags."""
    d = df.copy()
    X, _ = standardize(d)
    w = learn_weights(d, X, d["R"].to_numpy(float), 1.0)
    d["impact"] = X @ w * 2                           # round-share contribution, as in the model
    # opponent-adjusted impact: add back the average opponent impact sum (crude, per map)
    side = d.groupby(["game_id", "team"])["impact"].sum()
    d["impact"] += d.set_index(["game_id", "opp"]).index.map(side).to_numpy() / 5
    d["hs"] = d["hs"].fillna(d["hs"].median())
    for c in ["kpr", "dpr", "apr", "adr", "hs"]:
        g = d.groupby("role")[c]
        d[c + "_z"] = ((d[c] - g.transform("mean")) / g.transform("std").replace(0, np.nan)).fillna(0.0)
    d["open_r"] = (d["fk"] + d["fd"]) / d["R"]
    g = d.groupby("role")["open_r"]
    d["open_z"] = ((d["open_r"] - g.transform("mean")) / g.transform("std").replace(0, np.nan)).fillna(0.0)
    d["margin"] = (d["team_rounds"] - d["opp_rounds"]).abs()
    d["close"] = (d["margin"] <= 3) | (d["R"] > 24)
    d["decider_map"] = d["map_order"] == d["best_of"]
    d["won"] = d["team_rounds"] > d["opp_rounds"]
    # previous map of the same series, from this team's perspective
    prev = (d.drop_duplicates(["game_id", "team"])[["match_id", "team", "map_order", "won"]]
            .assign(map_order=lambda x: x["map_order"] + 1).rename(columns={"won": "prev_won"}))
    d = d.merge(prev, on=["match_id", "team", "map_order"], how="left")
    return d


def _shrunk_diff(x: pd.Series, mask: pd.Series, k: float = 6.0) -> float:
    a, b = x[mask], x[~mask]
    if len(a) == 0 or len(b) == 0:
        return 0.0
    return float((a.mean() - b.mean()) * (len(a) / (len(a) + k)))


def player_axes(m: pd.DataFrame, min_maps: int = 8) -> pd.DataFrame:
    rows = {}
    for pk, g in m.groupby("pkey"):
        if len(g) < min_maps:
            continue
        w = g["R"].to_numpy(float)
        fk, fd = g["fk"].sum(), g["fd"].sum()
        resid = g["impact"].fillna(0) - np.average(g["impact"].fillna(0), weights=w)
        noise = np.sqrt(np.average(1.0 / g["R"]) ) * 0.2       # expected sampling sd (approx.)
        rows[pk] = {
            "entry": np.average(g["open_z"], weights=w),
            "entry_eff": (fk + 10) / (fk + fd + 20) - 0.5,
            "support": np.average(g["apr_z"], weights=w),
            "survival": -np.average(g["dpr_z"], weights=w),
            "firepower": np.average(g["adr_z"], weights=w),
            "aim": np.average(g["hs_z"], weights=w),
            "volatility": float(np.sqrt(np.mean(resid ** 2))) - noise,
            "pressure": _shrunk_diff(g["impact"], g["close"]),
            "decider": _shrunk_diff(g["impact"], g["decider_map"]),
            "bounce": _shrunk_diff(g["impact"], g["prev_won"].eq(False) & g["prev_won"].notna())
                      - 0.0,
            "maps": len(g), "name": g["player"].iloc[-1], "team": g["team"].iloc[-1],
            "role": g["role"].mode().iat[0],
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def reliability(m: pd.DataFrame, min_maps: int = 8, seed: int = 0) -> pd.Series:
    """Split-half reliability (Spearman-Brown corrected) of each axis across players."""
    rng = np.random.default_rng(seed)
    games = m["game_id"].unique()
    out = []
    for rep in range(20):
        half = set(rng.choice(games, size=len(games) // 2, replace=False))
        a = player_axes(m[m["game_id"].isin(half)], min_maps // 2)
        b = player_axes(m[~m["game_id"].isin(half)], min_maps // 2)
        idx = a.index.intersection(b.index)
        r = {ax: np.corrcoef(a.loc[idx, ax].astype(float), b.loc[idx, ax].astype(float))[0, 1] for ax in AXES}
        out.append(r)
    r = pd.DataFrame(out).mean()
    return (2 * r / (1 + r)).clip(lower=-1)


# Axes shown in the app: only those that replicate as stable traits
# (split-half reliability >= ~0.3). Psychological axes (pressure, decider,
# bounce) do not replicate from per-map stats and are left out.
STYLE_AXES = [
    {"key": "entry", "label": "첫 교전", "desc": "첫 교전(선킬·선데스)에 나서는 빈도"},
    {"key": "firepower", "label": "화력", "desc": "라운드당 피해량"},
    {"key": "aim", "label": "조준", "desc": "헤드샷 비율"},
    {"key": "survival", "label": "생존", "desc": "라운드당 데스가 적은 정도"},
    {"key": "support", "label": "지원", "desc": "라운드당 어시스트"},
    {"key": "steady", "label": "일관성", "desc": "맵마다 경기력 편차가 적은 정도"},
]


def style_percentiles(df: pd.DataFrame, as_of, days: int = 365, min_maps: int = 10) -> dict:
    """{pkey: {axis: percentile 0-100}} among players with >= min_maps maps in the window.

    Axes are role-relative, so 100 on 'entry' means the most first-duel-heavy
    player *of his role*, not simply a duelist.
    """
    as_of = pd.Timestamp(as_of)
    win = df[(df["date"] < as_of) & (df["date"] >= as_of - pd.Timedelta(days=days))]
    if win.empty:
        return {}
    ax = player_axes(map_level(win), min_maps=min_maps)
    if ax.empty:
        return {}
    ax["steady"] = -ax["volatility"].astype(float)
    out = {}
    pct = {a["key"]: ax[a["key"]].astype(float).rank(pct=True) * 100 for a in STYLE_AXES}
    for pk in ax.index:
        out[str(pk)] = {k: round(float(v[pk]), 0) for k, v in pct.items()}
        out[str(pk)]["maps"] = int(ax.loc[pk, "maps"])
    return out
