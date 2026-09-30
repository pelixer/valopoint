"""Two-level Elo: team rating + region rating.

Effective strength = team_rating + region_rating.
- Domestic matches: region offsets cancel, only team ratings move.
- International matches: the team AND its region are updated, so a region that
  keeps beating others gets a higher offset that carries to its other teams.
  This is how regional-league results are linked to global-event strength.
Ratings decay toward the region mean when a team is inactive (roster/season churn).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from .data import Match


@dataclass
class Params:
    base: float = 1500.0
    k_team: float = 24.0
    k_region: float = 6.0          # region offset moves only on INTL matches
    k_intl_boost: float = 1.5      # INTL results are more informative for teams
    scale: float = 400.0
    margin_weight: float = 0.5     # 0 disables score/round margin scaling
    decay_days: float = 180.0      # half-life of pull-to-region-mean when inactive
    intl_weight: float = 1.0       # multiply K for INTL events (e.g. Champions)


@dataclass
class RatingBook:
    params: Params = field(default_factory=Params)
    team: dict[str, float] = field(default_factory=dict)
    team_region: dict[str, str] = field(default_factory=dict)
    region: dict[str, float] = field(default_factory=dict)
    last_seen: dict[str, date] = field(default_factory=dict)

    def _get(self, t: str, reg: str) -> float:
        if t not in self.team:
            self.team[t] = self.params.base
            self.team_region[t] = reg
        self.region.setdefault(reg, 0.0)
        return self.team[t]

    def strength(self, t: str) -> float:
        reg = self.team_region.get(t)
        return self.team.get(t, self.params.base) + self.region.get(reg, 0.0)

    def map_win_prob(self, a: str, b: str) -> float:
        d = self.strength(a) - self.strength(b)
        return 1.0 / (1.0 + 10 ** (-d / self.params.scale))

    def _decay(self, t: str, today: date) -> None:
        last = self.last_seen.get(t)
        if last is None:
            return
        gap = (today - last).days
        if gap <= 0:
            return
        w = 1 - 0.5 ** (gap / self.params.decay_days)
        self.team[t] += (self.params.base - self.team[t]) * w

    def update(self, m: Match) -> None:
        p = self.params
        self._get(m.team_a, m.region_a)
        self._get(m.team_b, m.region_b)
        self._decay(m.team_a, m.date)
        self._decay(m.team_b, m.date)

        # series-level expected share of maps ~ map win prob
        exp_a = self.map_win_prob(m.team_a, m.team_b)
        maps = m.score_a + m.score_b
        act_a = m.score_a / maps if maps else 0.5
        if m.rounds_a is not None and m.rounds_b is not None and p.margin_weight > 0:
            tot = m.rounds_a + m.rounds_b
            if tot:
                act_a = (1 - p.margin_weight) * act_a + p.margin_weight * (m.rounds_a / tot)
        # winner-emphasis: keep sign of result correct
        winner_bonus = 1.0 + 0.25 * math.log(1 + maps)
        delta = (act_a - exp_a) * winner_bonus

        k = p.k_team * (p.k_intl_boost * p.intl_weight if m.international else 1.0)
        self.team[m.team_a] += k * delta
        self.team[m.team_b] -= k * delta
        if m.international:
            self.region[m.region_a] += p.k_region * delta
            self.region[m.region_b] -= p.k_region * delta
        self.last_seen[m.team_a] = self.last_seen[m.team_b] = m.date


def fit(matches: list[Match], params: Params | None = None) -> RatingBook:
    book = RatingBook(params or Params())
    for m in matches:
        book.update(m)
    return book


def power_table(book: RatingBook) -> list[tuple[str, str, float, float]]:
    """(team, region, effective rating, power score 0-100 via logistic vs average)."""
    rows = []
    strengths = {t: book.strength(t) for t in book.team}
    mean = sum(strengths.values()) / len(strengths)
    for t, s in strengths.items():
        score = 100.0 / (1.0 + 10 ** (-(s - mean) / book.params.scale))
        rows.append((t, book.team_region[t], s, score))
    rows.sort(key=lambda r: -r[2])
    return rows
