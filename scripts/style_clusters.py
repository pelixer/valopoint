import numpy as np, pandas as pd
from valopoint.dataset import load
from valopoint.styles import map_level, player_axes
AX = ["entry", "support", "survival", "firepower", "aim", "volatility"]
df = load('data')
m = map_level(df[df.date >= '2025-07-01'])               # z-scores on a wide base
s2 = player_axes(m[m.event_id == 2776], min_maps=10)
Z = s2[AX].astype(float); Z = (Z - Z.mean()) / Z.std()

def kmeans(X, k, seed):
    rng = np.random.default_rng(seed); C = X[rng.choice(len(X), k, replace=False)]
    for _ in range(100):
        lab = ((X[:, None] - C[None]) ** 2).sum(-1).argmin(1)
        C2 = np.array([X[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)])
        if np.allclose(C, C2): break
        C = C2
    return lab, C

def silhouette(X, lab):
    D = np.sqrt(((X[:, None] - X[None]) ** 2).sum(-1)); s = []
    for i in range(len(X)):
        same = lab == lab[i]; a = D[i, same].sum() / max(same.sum() - 1, 1)
        b = min(D[i, lab == j].mean() for j in set(lab) if j != lab[i]); s.append((b - a) / max(a, b))
    return np.mean(s)

X = Z.to_numpy()
best = None
for k in range(3, 8):
    for seed in range(20):
        lab, C = kmeans(X, k, seed); sc = silhouette(X, lab)
        if best is None or sc > best[0] + 1e-9 and k <= 7: best = (sc, k, lab, C) if (best is None or sc > best[0]) else best
    print(k, round(max(silhouette(X, kmeans(X, k, s)[0]) for s in range(20)), 3))
sc, k, lab, C = best
print("chosen k", k, "silhouette", round(sc, 3))
s2["cluster"] = lab
cent = pd.DataFrame(C, columns=AX).round(2); cent["n"] = pd.Series(lab).value_counts().sort_index()
cent["roles"] = [dict(s2[s2.cluster == j].role.value_counts()) for j in range(k)]
print(cent.to_string())
for j in range(k):
    g = s2[s2.cluster == j]
    print(f"\n== cluster {j}"); print(g.assign(**{a: Z.loc[g.index, a].round(1) for a in AX})[["name", "team", "role", "maps"] + AX].to_string())
s2.assign(**{a + "_z": Z[a] for a in AX}).to_csv('/tmp/claude-0/s2_styles.csv')
