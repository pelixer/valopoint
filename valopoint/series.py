"""Series win probability from single-map win probability."""
from __future__ import annotations

from functools import lru_cache
from math import comb


def series_win_prob(p: float, best_of: int) -> float:
    """P(team wins Bo-N) with iid map win prob p."""
    need = best_of // 2 + 1
    return sum(comb(need - 1 + k, k) * p**need * (1 - p) ** k for k in range(need))
