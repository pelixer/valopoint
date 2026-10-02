"""Does a team x map result residual (beyond player PP) improve map prediction? Rolling OOS."""
import numpy as np, pandas as pd
from valopoint.dataset import load, games
from valopoint.model import Params, fit, logit, win_prob_from_q, sigmoid

df = load('data')
lineup = df.groupby(["game_id", "team"])["pkey"].apply(list).to_dict()
g = games(df).sort_values('date')
both = g.copy()
pairs = g[(g.team < g.opp) & (g.date >= '2025-04-01')].copy()
pairs['week'] = pairs.date.dt.to_period('W').dt.start_time
rows = []
for wk, gw in pairs.groupby('week'):
    mod = fit(df, Params(), as_of=wk)
    # OOS model prob for every side-map in the prior year, to build residuals (team-map over/under-performance)
    prior = both[(both.date < wk) & (both.date >= wk - pd.Timedelta(days=365))]
    for r in gw.itertuples():
        ra, rb = lineup[(r.game_id, r.team)], lineup[(r.game_id, r.opp)]
        dS = mod.team_strength(ra, r.map) - mod.team_strength(rb, r.map)
        rows.append(dict(game_id=r.game_id, date=r.date, event_id=r.event_id, team=r.team, opp=r.opp, map=r.map,
                         base=float(logit(win_prob_from_q(0.5 + dS))), win=r.win))
R = pd.DataFrame(rows)
# residual of each side-map vs the model's own (OOS) prediction, from the team's perspective
side = pd.concat([R.assign(t=R.team, res=R.win - sigmoid(0.6 * R.base)),
                  R.assign(t=R.opp, res=(1 - R.win) - (1 - sigmoid(0.6 * R.base)))])
def feat(row, k):
    out = []
    for t in (row.team, row.opp):
        h = side[(side.t == t) & (side.map == row.map) & (side.date < row.date) & (side.date >= row.date - pd.Timedelta(days=365))]
        o = side[(side.t == t) & (side.date < row.date) & (side.date >= row.date - pd.Timedelta(days=365))]
        out.append(h.res.sum() / (len(h) + k) - o.res.sum() / (len(o) + k))   # map-specific beyond overall form
    form = []
    for t in (row.team, row.opp):
        o = side[(side.t == t) & (side.date < row.date) & (side.date >= row.date - pd.Timedelta(days=120))]
        form.append(o.res.sum() / (len(o) + k))
    return out[0] - out[1], form[0] - form[1]
for k in (5, 15):
    F = np.array([feat(r, k) for r in R.itertuples()])
    R[f'tm{k}'], R[f'form{k}'] = F[:, 0], F[:, 1]
R.to_pickle('/tmp/claude-0/teammap.pkl')

def rl(X, y, l2):
    th = np.zeros(X.shape[1]); P = np.eye(X.shape[1]) * l2; P[0, 0] = 1e-6
    for _ in range(30):
        mu = 1 / (1 + np.exp(-X @ th)); th += np.linalg.solve((X * (mu * (1 - mu))[:, None]).T @ X + P, X.T @ (y - mu) - P @ th)
    return th
evs = R[R.date >= '2026-01-01'].groupby('event_id').date.min().sort_values().index
L = {}
for name, cols in [("PP", []), ("PP+teammap5", ["tm5"]), ("PP+teammap15", ["tm15"]), ("PP+form15", ["form15"]), ("PP+teammap15+form15", ["tm15", "form15"])]:
    out = []
    for e in evs:
        tr = R[R.date < R[R.event_id == e].date.min()]; te = R[R.event_id == e]
        X = lambda d: np.column_stack([d.base] + [d[c] for c in cols])
        p = np.clip(1 / (1 + np.exp(-X(te) @ rl(X(tr), tr.win.to_numpy(), 2.0))), 1e-6, 1 - 1e-6); y = te.win.to_numpy()
        out += list(-(y * np.log(p) + (1 - y) * np.log(1 - p)))
    L[name] = np.array(out)
rng = np.random.default_rng(0)
for k, v in L.items():
    d = L["PP"] - v; bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(3000)]
    print(f"{k:22s} logloss {v.mean():.4f}  gain {d.mean():+.4f}  95%CI [{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}]")
