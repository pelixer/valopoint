"""Walk-forward evaluation: predict each match with ratings from strictly earlier data."""
from __future__ import annotations

import math

from .data import Match
from .rating import Params, RatingBook
from .series import series_win_prob


def backtest(matches: list[Match], params: Params | None = None, intl_only: bool = True,
             warmup: int = 50) -> dict:
    book = RatingBook(params or Params())
    ll = brier = correct = n = 0.0
    for i, m in enumerate(matches):
        if i >= warmup and (m.international or not intl_only) and m.score_a != m.score_b:
            book._get(m.team_a, m.region_a); book._get(m.team_b, m.region_b)
            p = series_win_prob(book.map_win_prob(m.team_a, m.team_b), m.best_of)
            y = 1.0 if m.score_a > m.score_b else 0.0
            p = min(max(p, 1e-6), 1 - 1e-6)
            ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
            brier += (p - y) ** 2
            correct += (p > 0.5) == (y == 1.0)
            n += 1
        book.update(m)
    n = max(n, 1)
    return {"n": int(n), "log_loss": ll / n, "brier": brier / n, "accuracy": correct / n}
