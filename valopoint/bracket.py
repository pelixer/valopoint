"""Generic bracket simulator (any single/double-elim/GSL format) via a match DAG.

Bracket JSON:
{
  "name": "Masters ...",
  "teams": ["A", "B", ...],            # seeded list; refer to as "S1".."Sn" (1-based) or by name
  "matches": [
    {"id": "UB1", "a": "S1", "b": "S8", "best_of": 3},
    {"id": "LB1", "a": "L:UB1", "b": "L:UB2", "best_of": 3},
    {"id": "GF",  "a": "W:UB3", "b": "W:LB4", "best_of": 5}
  ],
  "placements": {"GF": ["W", "L"]}      # optional, informational
}
Slot refs: "S<n>", team name, "W:<id>" winner of match, "L:<id>" loser of match.
Matches must be listed in a valid execution order.
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict

from .rating import RatingBook
from .series import series_win_prob


def load_bracket(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolve(ref: str, seeds: list[str], res: dict[str, tuple[str, str]]) -> str:
    if ref.startswith("W:"):
        return res[ref[2:]][0]
    if ref.startswith("L:"):
        return res[ref[2:]][1]
    if ref.startswith("S") and ref[1:].isdigit():
        return seeds[int(ref[1:]) - 1]
    return ref


def simulate(book: RatingBook, bracket: dict, n: int = 20000, seed: int = 0) -> dict:
    rng = random.Random(seed)
    seeds = bracket["teams"]
    matches = bracket["matches"]
    final_id = bracket.get("final", matches[-1]["id"])
    champs: Counter = Counter()
    reach: dict[str, Counter] = defaultdict(Counter)   # team -> match id -> times played
    cache: dict[tuple[str, str, int], float] = {}

    def p_series(a, b, bo):
        k = (a, b, bo)
        if k not in cache:
            cache[k] = series_win_prob(book.map_win_prob(a, b), bo)
        return cache[k]

    for _ in range(n):
        res: dict[str, tuple[str, str]] = {}
        for m in matches:
            a = _resolve(m["a"], seeds, res)
            b = _resolve(m["b"], seeds, res)
            reach[a][m["id"]] += 1
            reach[b][m["id"]] += 1
            win = a if rng.random() < p_series(a, b, m.get("best_of", 3)) else b
            res[m["id"]] = (win, b if win == a else a)
        champs[res[final_id][0]] += 1

    return {
        "champion": {t: champs[t] / n for t in seeds},
        "reach": {t: {mid: c / n for mid, c in reach[t].items()} for t in seeds},
    }


def match_forecast(book: RatingBook, a: str, b: str, best_of: int = 3) -> dict:
    p_map = book.map_win_prob(a, b)
    return {"map": p_map, "series": series_win_prob(p_map, best_of)}
