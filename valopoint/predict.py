"""Series prediction on top of the player model: rosters, map pool, veto, gamma fit."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .model import PlayerModel, logit, sigmoid, win_prob_from_q

# VCT veto orders (A = team with first ban). 'b'=ban, 'p'=pick, 'd'=decider
VETO = {
    1: "ABABAB",        # 6 bans -> decider
    3: "ABabAB",        # ban ban pick pick ban ban -> decider
    5: "ABabab",        # ban ban pick pick pick pick -> decider
}


def rosters(df: pd.DataFrame, as_of=None) -> dict[str, list[str]]:
    """Team -> the five players of its most recent map before as_of."""
    d = df if as_of is None else df[df["date"] < pd.Timestamp(as_of)]
    last_game = d.sort_values(["date", "match_id", "map_order"]).groupby("team")["game_id"].last()
    sub = d[d["game_id"].isin(last_game.values)]
    sub = sub[sub.apply(lambda r: last_game.get(r["team"]) == r["game_id"], axis=1)]
    return sub.groupby("team")["pkey"].apply(list).to_dict()


def team_region(df: pd.DataFrame) -> dict[str, str]:
    return df.groupby("team")["team_region"].agg(lambda s: s.mode().iat[0]).to_dict()


def map_pool(df: pd.DataFrame, as_of=None, days: int = 120, size: int = 7) -> list[str]:
    d = df if as_of is None else df[df["date"] < pd.Timestamp(as_of)]
    recent = d[d["date"] >= d["date"].max() - pd.Timedelta(days=days)]
    return recent.groupby("map")["game_id"].nunique().sort_values(ascending=False).index[:size].tolist()


def series_prob_ordered(ps: list[float]) -> float:
    """P(A wins series) when maps are played in order with win probs ps (first to ceil(n/2))."""
    need = len(ps) // 2 + 1
    dist = {(0, 0): 1.0}
    win = 0.0
    for p in ps:
        nd = {}
        for (a, b), pr in dist.items():
            for (a2, b2), q in (((a + 1, b), p), ((a, b + 1), 1 - p)):
                if a2 == need:
                    win += pr * q
                elif b2 == need:
                    continue
                else:
                    nd[(a2, b2)] = nd.get((a2, b2), 0.0) + pr * q
        dist = nd
    return win


def veto_maps(pmap: dict[str, float], best_of: int, a_first: bool = True) -> list[str]:
    """Greedy veto: each side bans its worst map / picks its best. Returns play order."""
    order = VETO.get(best_of, VETO[3])
    left = list(pmap)
    picks = []
    for ch in order:
        if len(left) <= 1:
            break
        a_turn = (ch.upper() == "A") == a_first
        score = (lambda m: pmap[m]) if a_turn else (lambda m: 1 - pmap[m])
        if ch.isupper():   # ban own worst
            left.remove(min(left, key=score))
        else:              # pick own best
            m = max(left, key=score)
            left.remove(m)
            picks.append(m)
    return picks + left[:1]


def series_forecast(model: PlayerModel, ra: list[str], rb: list[str], rega: str, regb: str,
                    pool: list[str], best_of: int = 3) -> dict:
    pmap = {m: model.map_win_prob(ra, rb, m, rega, regb) for m in pool}
    out = []
    for a_first in (True, False):
        maps = veto_maps(pmap, best_of, a_first)
        out.append((maps, series_prob_ordered([pmap[m] for m in maps])))
    return {"maps": pmap, "series": float(np.mean([o[1] for o in out])),
            "veto": {"a_first": out[0][0], "b_first": out[1][0]}}


def fit_gamma(records: pd.DataFrame, as_of, half_life: float, l2: float,
              iters: int = 25) -> tuple[float, dict]:
    """Fit calibration slope beta and region result offsets gamma on international
    map results, using each map's OUT-OF-SAMPLE strength gap (from walk-forward).

    logit P(A wins) = beta * logit(P_theory(dS)) + gamma[rA] - gamma[rB]
    """
    r = records[records["intl"] & (records["region_a"] != records["region_b"])]
    if len(r) < 20:
        return 1.0, {}
    regs = sorted(set(r["region_a"]) | set(r["region_b"]))
    idx = {g: i for i, g in enumerate(regs)}
    n, k = len(r), len(regs)
    Z = np.zeros((n, 1 + k))
    Z[:, 0] = logit(win_prob_from_q(0.5 + r["dS"].to_numpy()))
    Z[np.arange(n), 1 + r["region_a"].map(idx).to_numpy()] += 1
    Z[np.arange(n), 1 + r["region_b"].map(idx).to_numpy()] -= 1
    y = r["win"].to_numpy()
    age = (pd.Timestamp(as_of) - pd.to_datetime(r["date"])).dt.days.to_numpy()
    wt = 0.5 ** (age / half_life)
    # penalties: beta shrunk toward 1 lightly, gamma toward 0
    P = np.diag([1.0] + [l2] * k)
    prior = np.zeros(1 + k); prior[0] = 1.0
    theta = prior.copy()
    for _ in range(iters):
        mu = sigmoid(Z @ theta)
        g = Z.T @ (wt * (y - mu)) - P @ (theta - prior)
        H = (Z * (wt * mu * (1 - mu))[:, None]).T @ Z + P
        theta = theta + np.linalg.solve(H, g)
    gam = theta[1:] - theta[1:].mean()
    return float(theta[0]), {g: float(gam[i]) for g, i in idx.items()}
