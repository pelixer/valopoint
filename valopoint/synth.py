"""Synthetic league generator for tests/demo (NOT real VCT data)."""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta

from .series import series_win_prob

REGIONS = {"AMER": 40, "EMEA": 30, "PAC": 60, "CN": -60}  # hidden true regional offsets


def generate(path: str, seed: int = 1) -> None:
    rng = random.Random(seed)
    teams = {r: [(f"{r}_T{i}", rng.gauss(0, 80)) for i in range(1, 9)] for r in REGIONS}
    rows = []
    d = date(2025, 1, 10)

    def play(a, ra, sa, b, rb, sb, ev, reg, bo=3):
        p = 1 / (1 + 10 ** (-((sa + REGIONS[ra]) - (sb + REGIONS[rb])) / 400))
        need = bo // 2 + 1
        wa = wb = 0
        while wa < need and wb < need:
            if rng.random() < p: wa += 1
            else: wb += 1
        rows.append([d.isoformat(), ev, reg, a, b, ra, rb, wa, wb, bo, "", ""])

    for season, intl in enumerate(["Masters", "Champions"]):
        for week in range(6):  # domestic round-robin chunks
            for r, ts in teams.items():
                for i in range(len(ts)):
                    for j in range(i + 1, len(ts)):
                        if rng.random() < 0.25:
                            play(ts[i][0], r, ts[i][1], ts[j][0], r, ts[j][1], f"{r} League", r)
            d += timedelta(days=7)
        top = [t for r in REGIONS for t in sorted(teams[r], key=lambda x: -x[1])[:3]]
        for _ in range(30):
            (a, sa), (b, sb) = rng.sample(top, 2)
            ra, rb = a.split("_")[0], b.split("_")[0]
            if ra != rb:
                play(a, ra, sa, b, rb, sb, f"{intl} {2025+season}", "INTL", 3)
            d += timedelta(days=1)
        d += timedelta(days=14)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow("date,event,region,team_a,team_b,region_a,region_b,score_a,score_b,best_of,rounds_a,rounds_b".split(","))
        w.writerows(rows)
