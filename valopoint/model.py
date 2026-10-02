"""Player power point (PP) model.

Pipeline
1. Per-round stats (KPR, DPR, APR, FKPR, FDPR, ADR, KAST) are standardized
   *within role* (duelist / initiator / controller / sentinel), so a role that
   naturally produces more kills is not rated higher for doing its job.
2. Stat weights are LEARNED, not hand-picked: ridge regression of each map's
   round-win share on the two teams' summed standardized stats. A player's
   per-map value v = w·x is then in units of "round-win share contributed".
3. Opponent adjustment: stats are depressed against strong opponents, so each
   observation is shifted by opp_adj * (opponent team strength)/5.
4. Hierarchical empirical-Bayes decomposition (backfitting):
       theta(player, map, agent) = region + player + player×agent + player×map
   Each level is a precision-weighted mean shrunk toward 0 with a strength
   k = sigma² / tau² estimated from the data (method of moments). Small samples
   (e.g. 2 maps of Omen on Lotus) therefore stay close to the player's overall
   value; large samples speak for themselves. Rounds are the weight unit,
   combined with exponential time decay, and outliers are Huber-clipped.
5. Region offsets are identified only by international matches (domestic
   matches cancel them), i.e. they translate every league onto one global scale.

PP scale: 100 + 1000*theta. 10 PP = +1%p expected round-win share for the team.
A team's strength on a map is the sum of its five players' theta.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

from .dataset import FEATURES

MAIN_REGIONS = ["AMER", "EMEA", "PAC", "CN"]


@dataclass
class Params:
    half_life_days: float = 180.0   # time decay of observations
    window_days: float = 730.0      # 2 years of data
    w_intl: float = 1.5             # weight multiplier for international maps
    w_live: float = 1.0             # extra multiplier for the event being predicted
    opp_adj: float = 1.0            # strength of opponent adjustment
    huber_c: float = 2.5            # clip standardized residuals at +-c
    ridge: float = 1.0              # ridge penalty for stat weights
    iters: int = 8
    agent_prior: float = 3.0        # pseudo-maps pulling map agent-mix to overall mix
    k_mult: float = 1.0             # multiply estimated shrinkage (tuning knob)
    beta: float = 1.0               # calibration slope (fitted from intl results)
    gamma_l2: float = 20.0          # ridge on region result offsets
    k_dev: float | None = 2000.0    # fixed shrinkage (rounds) for player x map / player x agent; None = estimated

    def to_dict(self):
        return asdict(self)


def pp(theta):
    return 100.0 + 1000.0 * np.asarray(theta)


# ---------------------------------------------------------------- helpers

def _decay(dates: pd.Series, as_of: pd.Timestamp, half_life: float) -> np.ndarray:
    age = (as_of - dates).dt.days.to_numpy().clip(min=0)
    return 0.5 ** (age / half_life)


def _eb_shrink(codes: np.ndarray, ng: int, resid: np.ndarray, w: np.ndarray, R: np.ndarray,
               k_mult: float, min_w: float = 100.0, half: np.ndarray | None = None,
               k_fixed: float | None = None):
    """Precision-weighted group means shrunk toward 0 (empirical Bayes).

    One-way random-effects variance components: the per-round noise variance is
    the pooled WITHIN-group variance (residuals around each group's own mean), and
    the between-group variance tau2 = E[mean^2] - E[sampling var of mean], using
    the exact sampling variance of a decay-weighted mean. k = sigma2 / tau2 is the
    shrinkage strength in rounds.
    """
    sw = np.bincount(codes, weights=w, minlength=ng)
    swr = np.bincount(codes, weights=w * resid, minlength=ng)
    mean = swr / np.maximum(sw, 1e-12)
    e = resid - mean[codes]
    dec = w / R
    n_obs = np.bincount(codes, minlength=ng)
    dof = max(len(resid) - int((n_obs > 0).sum()), 1)
    sigma2 = float(np.sum(dec * R * e * e) / np.sum(dec) * len(resid) / dof)
    ok = sw >= min_w
    if half is not None:
        # Split-half variance components (no noise-model assumption): with the
        # data split into two halves by MATCH, the two group means share only the
        # true group effect, so their covariance estimates tau2; their difference
        # measures sampling noise, giving the effective per-round-weight variance.
        def gm(mask):
            swh = np.bincount(codes[mask], weights=w[mask], minlength=ng)
            return np.bincount(codes[mask], weights=(w * resid)[mask], minlength=ng) / np.maximum(swh, 1e-12), swh
        a, swa = gm(half)
        b, swb = gm(~half)
        both = (swa > 0) & (swb > 0)
        if both.sum() >= 10:
            eff = 1.0 / (1.0 / swa[both] + 1.0 / swb[both])
            tau2 = float(np.average(a[both] * b[both], weights=eff))
            sigma2 = float(np.mean((a[both] - b[both]) ** 2 * eff))
        else:
            tau2 = 0.0
    elif ok.sum() >= 3:
        var_mean = sigma2 * np.bincount(codes, weights=w * w / R, minlength=ng)[ok] / sw[ok] ** 2
        tau2 = float(np.mean(mean[ok] ** 2 - var_mean))
    else:
        tau2 = 0.0
    tau2 = max(tau2, 1e-7)
    k = k_mult * sigma2 / tau2 if k_fixed is None else k_fixed
    return swr / (sw + k), k, tau2


def _group_mean(x: np.ndarray, codes: np.ndarray, w: np.ndarray, ng: int) -> np.ndarray:
    sw = np.bincount(codes, weights=w, minlength=ng)
    return np.bincount(codes, weights=w * x, minlength=ng) / np.maximum(sw, 1e-12)


def win_prob_from_q(q):
    """P(win a map) given iid round-win prob q (first to 13, OT win by 2)."""
    q = np.clip(np.asarray(q, dtype=float), 0.02, 0.98)
    r = 1 - q
    from math import comb
    p = sum(comb(12 + k, k) * q ** 13 * r ** k for k in range(12))
    tie = comb(24, 12) * q ** 12 * r ** 12
    return p + tie * q * q / (q * q + r * r)


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


# ---------------------------------------------------------------- model

@dataclass
class PlayerModel:
    params: Params
    as_of: pd.Timestamp
    std: dict                       # role -> (mean vec, sd vec)
    w: np.ndarray                   # stat weights
    region: dict                    # region -> offset (theta units)
    player: pd.DataFrame            # pkey -> u, name, team, region, rounds
    p_agent: pd.DataFrame           # (pkey, agent) -> dev, rounds
    p_map: pd.DataFrame             # (pkey, map) -> dev, rounds
    agent_mix: pd.DataFrame         # (pkey, map, agent) -> weight
    diag: dict = field(default_factory=dict)
    gamma: dict = field(default_factory=dict)   # region result offsets (logit units)
    rows: pd.DataFrame | None = None            # per player-map opponent-adjusted performance (theta units)

    # ---- lookups
    def theta(self, pkey: str, map_: str | None = None, agent: str | None = None,
              region: str | None = None) -> float:
        pl = self.player.loc[pkey] if pkey in self.player.index else None
        reg = region or (pl["region"] if pl is not None else "UNK")
        t = self.region.get(reg, 0.0) + (pl["u"] if pl is not None else 0.0)
        if map_ is not None:
            t += self._pm.get((pkey, map_), 0.0)
        if agent is not None:
            t += self._pa.get((pkey, agent), 0.0)
        elif map_ is not None:
            t += self.expected_agent_dev(pkey, map_)
        return float(t)

    def expected_agent_dev(self, pkey: str, map_: str) -> float:
        mix = self._mix.get((pkey, map_)) or self._mix.get((pkey, None))
        if not mix:
            return 0.0
        return float(sum(wt * self._pa.get((pkey, a), 0.0) for a, wt in mix.items()))

    def team_strength(self, roster: list[str], map_: str, region: str | None = None) -> float:
        return sum(self.theta(p, map_, region=region) for p in roster)

    def map_win_prob(self, roster_a, roster_b, map_, region_a, region_b) -> float:
        s = self.team_strength(roster_a, map_, region_a) - self.team_strength(roster_b, map_, region_b)
        return float(self.calibrated(s, region_a, region_b))

    def calibrated(self, dS, region_a, region_b):
        base = logit(win_prob_from_q(0.5 + np.asarray(dS)))
        g = self.gamma.get(region_a, 0.0) - self.gamma.get(region_b, 0.0)
        return sigmoid(self.params.beta * base + g)

    def __post_init__(self):
        self._pa = {(r.pkey, r.agent): r.dev for r in self.p_agent.itertuples()}
        self._pm = {(r.pkey, r.map): r.dev for r in self.p_map.itertuples()}
        self._mix: dict = {}
        for (pk, m), g in self.agent_mix.groupby(["pkey", "map"], dropna=False):
            self._mix[(pk, m if isinstance(m, str) else None)] = dict(zip(g["agent"], g["weight"]))


def standardize(df: pd.DataFrame, std: dict | None = None):
    X = np.zeros((len(df), len(FEATURES)))
    if std is None:
        std = {}
        for role, g in df.groupby("role"):
            wts = g["R"].to_numpy()
            vals = g[FEATURES].to_numpy()
            mu = np.average(vals, axis=0, weights=wts)
            sd = np.sqrt(np.average((vals - mu) ** 2, axis=0, weights=wts)) + 1e-9
            std[role] = (mu, sd)
    allmu = np.mean([v[0] for v in std.values()], axis=0)
    allsd = np.mean([v[1] for v in std.values()], axis=0)
    roles = df["role"].to_numpy()
    vals = df[FEATURES].to_numpy()
    for role in np.unique(roles):
        mu, sd = std.get(role, (allmu, allsd))
        idx = roles == role
        X[idx] = (vals[idx] - mu) / sd
    return X, std


def learn_weights(df: pd.DataFrame, X: np.ndarray, wrow: np.ndarray, ridge: float) -> np.ndarray:
    """Ridge: share_A - 0.5 ~ w·(sum x_A - sum x_B) / 2  (so sum over a team of w·x = its round edge)."""
    key = df["game_id"].astype(str) + "|" + df["team"].astype(str)
    codes, uniq = pd.factorize(key)
    Xt = np.zeros((len(uniq), X.shape[1]))
    np.add.at(Xt, codes, X)
    side = df.groupby(key.to_numpy(), sort=False).agg(
        opp=("opp", "first"), game=("game_id", "first"),
        tr=("team_rounds", "first"), orr=("opp_rounds", "first"))
    side = side.loc[uniq]
    opp_key = side["game"].astype(str) + "|" + side["opp"].astype(str)
    pos = pd.Series(np.arange(len(uniq)), index=uniq)
    has = opp_key.isin(pos.index).to_numpy()
    oi = pos.reindex(opp_key[has]).to_numpy()
    D = (Xt[has] - Xt[oi]) / 2.0
    y = (side["tr"] / (side["tr"] + side["orr"])).to_numpy()[has] - 0.5
    gw = np.bincount(codes, weights=wrow, minlength=len(uniq))[has] / 5.0
    A = D.T @ (D * gw[:, None]) + ridge * np.eye(D.shape[1])
    return np.linalg.solve(A, D.T @ (gw * y))


def fit(df: pd.DataFrame, params: Params | None = None, as_of=None,
        live_events: set | None = None) -> PlayerModel:
    p = params or Params()
    as_of = pd.Timestamp(as_of) if as_of is not None else df["date"].max() + pd.Timedelta(days=1)
    df = df[(df["date"] < as_of) & (df["date"] >= as_of - pd.Timedelta(days=p.window_days))].reset_index(drop=True)
    if df.empty:
        raise ValueError("no training data before as_of")

    decay = _decay(df["date"], as_of, p.half_life_days)
    mult = np.where(df["intl"].to_numpy(), p.w_intl, 1.0)
    if live_events:
        mult = mult * np.where(df["event_id"].isin(live_events).to_numpy(), p.w_live, 1.0)
    R = df["R"].to_numpy().astype(float)
    w = R * decay * mult

    X, std = standardize(df)
    wts = learn_weights(df, X, w, p.ridge)
    v = X @ wts

    # codes
    pc, pk_uni = pd.factorize(df["pkey"])
    # deterministic split of matches into two halves for variance components
    half = (pd.util.hash_array(df["match_id"].to_numpy()) % 2 == 0)
    rc, reg_uni = pd.factorize(df["team_region"])
    pa_key = df["pkey"] + "|" + df["agent"]
    pac, pa_uni = pd.factorize(pa_key)
    pm_key = df["pkey"] + "|" + df["map"]
    pmc, pm_uni = pd.factorize(pm_key)
    intl = df["intl"].to_numpy()
    side_key = df["game_id"].astype(str) + "|" + df["team"].astype(str)
    sc, side_uni = pd.factorize(side_key)
    opp_key = df["game_id"].astype(str) + "|" + df["opp"].astype(str)
    side_pos = pd.Series(np.arange(len(side_uni)), index=side_uni)
    oc = side_pos.reindex(opp_key).fillna(-1).astype(int).to_numpy()

    # each player's home region code = region of most of his weighted rounds
    preg = pd.DataFrame({"p": pc, "r": rc, "w": w}).groupby(["p", "r"])["w"].sum() \
        .reset_index().sort_values("w").groupby("p")["r"].last().reindex(range(len(pk_uni))).to_numpy()
    pa_player = pd.Series(pc).groupby(pac).first().reindex(range(len(pa_uni))).to_numpy()
    pm_player = pd.Series(pc).groupby(pmc).first().reindex(range(len(pm_uni))).to_numpy()

    delta = np.zeros(len(reg_uni))
    u = np.zeros(len(pk_uni))
    dpa = np.zeros(len(pa_uni))
    dpm = np.zeros(len(pm_uni))
    sigma2 = float(np.average(v ** 2 * R, weights=w))
    ks = {}
    main_mask = np.isin(reg_uni, MAIN_REGIONS)

    for _ in range(p.iters):
        fitted = delta[rc] + u[pc] + dpa[pac] + dpm[pmc]
        side_sum = np.bincount(sc, weights=fitted, minlength=len(side_uni))
        s_opp = np.where(oc >= 0, side_sum[np.maximum(oc, 0)], 0.0)
        t = v + p.opp_adj * s_opp / 5.0
        # Huber clipping against current fit
        e = t - fitted
        sig_row = np.sqrt(sigma2 / R)
        t = fitted + np.clip(e, -p.huber_c * sig_row, p.huber_c * sig_row)
        sigma2 = float(np.average((t - fitted) ** 2 * R, weights=w))

        # player level, then centred within region: region level lives in delta only
        # (otherwise delta and the mean of u drift against each other, unidentified)
        res = t - delta[rc] - dpa[pac] - dpm[pmc]
        u, ks["player"], _ = _eb_shrink(pc, len(pk_uni), res, w, R, p.k_mult, half=half)
        u -= _group_mean(u[pc], rc, w, len(reg_uni))[preg]
        # region offsets: identified by international maps only
        if intl.any():
            res = (t - u[pc] - dpa[pac] - dpm[pmc])[intl]
            d_new, ks["region"], _ = _eb_shrink(rc[intl], len(reg_uni), res, w[intl], R[intl], p.k_mult, min_w=100)
            if main_mask.any():
                d_new = d_new - d_new[main_mask].mean()
            delta = d_new
        # player x agent / player x map deviations, centred per player
        res = t - delta[rc] - u[pc] - dpm[pmc]
        dpa, ks["player_agent"], _ = _eb_shrink(pac, len(pa_uni), res, w, R, p.k_mult, min_w=60, half=half, k_fixed=p.k_dev)
        dpa -= _group_mean(dpa[pac], pc, w, len(pk_uni))[pa_player]
        res = t - delta[rc] - u[pc] - dpa[pac]
        dpm, ks["player_map"], _ = _eb_shrink(pmc, len(pm_uni), res, w, R, p.k_mult, min_w=60, half=half, k_fixed=p.k_dev)
        dpm -= _group_mean(dpm[pmc], pc, w, len(pk_uni))[pm_player]

    # ---- tables
    last = df.sort_values("date").groupby("pkey").tail(1).set_index("pkey")
    rounds = pd.Series(np.bincount(pc, weights=R, minlength=len(pk_uni)), index=pk_uni)
    player = pd.DataFrame({
        "u": u, "name": last.loc[pk_uni, "player"].to_numpy(),
        "team": last.loc[pk_uni, "team"].to_numpy(),
        "region": last.loc[pk_uni, "team_region"].to_numpy(),
        "rounds": rounds.to_numpy(),
    }, index=pd.Index(pk_uni, name="pkey"))

    def split(uni, dev, codes, col):
        parts = pd.Series(uni).str.split("|", n=1, expand=True)
        return pd.DataFrame({"pkey": parts[0], col: parts[1], "dev": dev,
                             "rounds": np.bincount(codes, weights=R, minlength=len(uni))})

    p_agent = split(pa_uni, dpa, pac, "agent")
    p_map = split(pm_uni, dpm, pmc, "map")

    # agent mix per (player, map), shrunk to the player's overall mix
    wm = df.assign(wt=decay)
    overall = wm.groupby(["pkey", "agent"])["wt"].sum()
    overall = overall / overall.groupby(level=0).transform("sum")
    per_map = wm.groupby(["pkey", "map", "agent"])["wt"].sum().rename("n").reset_index()
    per_map["prior"] = overall.reindex(pd.MultiIndex.from_frame(per_map[["pkey", "agent"]])).to_numpy()
    tot = per_map.groupby(["pkey", "map"])["n"].transform("sum")
    per_map["weight"] = (per_map["n"] + p.agent_prior * per_map["prior"]) / (tot + p.agent_prior)
    # renormalise (prior mass only covers agents already seen on this map)
    per_map["weight"] /= per_map.groupby(["pkey", "map"])["weight"].transform("sum")
    ov = overall.rename("weight").reset_index().assign(map=None)
    agent_mix = pd.concat([per_map[["pkey", "map", "agent", "weight"]], ov[["pkey", "map", "agent", "weight"]]])

    perf_rows = df[["pkey", "date", "event_id", "event", "intl", "map", "agent", "team", "opp",
                    "team_rounds", "opp_rounds", "match_id", "game_id"]].assign(R=R, perf=t)

    return PlayerModel(
        params=p, as_of=as_of, std=std, w=wts, rows=perf_rows,
        region={r: float(d) for r, d in zip(reg_uni, delta)},
        player=player, p_agent=p_agent, p_map=p_map, agent_mix=agent_mix,
        diag={"shrinkage_k_rounds": {k: float(v) for k, v in ks.items()},
              "sigma2_round": sigma2, "n_rows": int(len(df)),
              "weights": dict(zip(FEATURES, map(float, wts)))},
    )
