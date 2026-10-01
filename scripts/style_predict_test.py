"""Does adding play-style / matchup terms improve map prediction over PP alone? (rolling, out-of-sample)"""
import numpy as np, pandas as pd
from dataclasses import replace
from valopoint.dataset import load, games
from valopoint.model import Params, fit, logit, win_prob_from_q
from valopoint.styles import map_level, player_axes

AX = ["entry", "support", "survival", "firepower", "aim", "volatility"]
df = load('data')
m = map_level(df)
lineup = df.groupby(["game_id", "team"])["pkey"].apply(list).to_dict()
g = games(df); g = g[(g.team < g.opp) & (g.date >= '2025-04-01')].sort_values('date')
g['week'] = g.date.dt.to_period('W').dt.start_time

rows = []
ev_start = df.groupby('event_id').date.min()
style_cache = {}
for wk, gw in g.groupby('week'):
    mod = fit(df, Params(), as_of=wk)
    for r in gw.itertuples():
        es = ev_start[r.event_id]
        if es not in style_cache:
            prior = m[(m.date < es) & (m.date >= es - pd.Timedelta(days=365))]
            st = player_axes(prior, min_maps=8)
            z = st[AX].astype(float); style_cache[es] = ((z - z.mean()) / z.std()).fillna(0)
        S = style_cache[es]
        ra, rb = lineup[(r.game_id, r.team)], lineup[(r.game_id, r.opp)]
        dS = mod.team_strength(ra, r.map) - mod.team_strength(rb, r.map)
        A = S.reindex(ra).fillna(0); B = S.reindex(rb).fillna(0)
        mA, mB = A.mean(), B.mean()
        dec = float(r.map_order == r.best_of)
        feat = {f"d_{a}": mA[a] - mB[a] for a in AX}
        feat["x_entry_vs_surv"] = mA.entry * mB.survival - mB.entry * mA.survival
        feat["x_fire_vs_support"] = mA.firepower * mB.support - mB.firepower * mA.support
        feat["x_vol_decider"] = (mA.volatility - mB.volatility) * dec
        feat["x_spread_entry"] = A.entry.std() - B.entry.std()           # role balance
        rows.append(dict(date=r.date, event_id=r.event_id, base=float(logit(win_prob_from_q(0.5 + dS))),
                         win=r.win, intl=r.intl, **feat))
R = pd.DataFrame(rows)
R.to_pickle('/tmp/claude-0/style_rows.pkl')

def ridge_logit(X, y, l2, iters=30):
    th = np.zeros(X.shape[1]); P = np.eye(X.shape[1]) * l2; P[0, 0] = 1e-6
    for _ in range(iters):
        mu = 1 / (1 + np.exp(-X @ th)); H = (X * (mu * (1 - mu))[:, None]).T @ X + P
        th += np.linalg.solve(H, X.T @ (y - mu) - P @ th)
    return th

F = [c for c in R.columns if c.startswith(("d_", "x_"))]
test_events = R[R.date >= '2026-01-01'].groupby('event_id').date.min().sort_values().index
res = {}
for name, cols in [("PP only", []), ("PP + style means", [f"d_{a}" for a in AX]), ("PP + style + matchup", F)]:
    for l2 in ([1.0] if not cols else [5.0, 20.0, 80.0]):
        ll = []; acc = []
        for e in test_events:
            tr = R[R.date < R[R.event_id == e].date.min()]; te = R[R.event_id == e]
            X = lambda d: np.column_stack([d.base.to_numpy()] + [d[c].to_numpy() for c in cols])
            th = ridge_logit(X(tr), tr.win.to_numpy(), l2)
            p = np.clip(1 / (1 + np.exp(-X(te) @ th)), 1e-6, 1 - 1e-6); y = te.win.to_numpy()
            ll += list(-(y * np.log(p) + (1 - y) * np.log(1 - p))); acc += list((p > .5) == (y == 1))
        res[f"{name} (l2={l2})"] = (len(ll), np.mean(ll), np.mean(acc))
for k, (n, l, a) in res.items():
    print(f"{k:34s} n={n} logloss={l:.4f} acc={a:.3f}")
th = ridge_logit(np.column_stack([R.base] + [R[c] for c in F]), R.win.to_numpy(), 20.0)
print("coef (all data, l2=20):", dict(zip(["base"] + F, np.round(th, 3))))
