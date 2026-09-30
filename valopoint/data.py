"""Match data schema and CSV loader.

CSV columns (header required):
  date       YYYY-MM-DD
  event      event name
  region     league region (AMER, EMEA, PAC, CN, ...) or INTL for cross-region events
  team_a, team_b
  region_a, region_b   home region of each team (needed for INTL matches)
  score_a, score_b     maps won in the series
  best_of    1, 3 or 5
Optional: rounds_a, rounds_b (total rounds won across all maps) for margin weighting.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Match:
    date: date
    event: str
    region: str
    team_a: str
    team_b: str
    region_a: str
    region_b: str
    score_a: int
    score_b: int
    best_of: int = 3
    rounds_a: int | None = None
    rounds_b: int | None = None

    @property
    def international(self) -> bool:
        return self.region_a != self.region_b


def load_matches(path: str) -> list[Match]:
    out: list[Match] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            def opt(k):
                v = (row.get(k) or "").strip()
                return int(v) if v else None
            out.append(Match(
                date=date.fromisoformat(row["date"].strip()),
                event=row["event"].strip(),
                region=row["region"].strip(),
                team_a=row["team_a"].strip(),
                team_b=row["team_b"].strip(),
                region_a=row["region_a"].strip(),
                region_b=row["region_b"].strip(),
                score_a=int(row["score_a"]),
                score_b=int(row["score_b"]),
                best_of=int(row.get("best_of") or 3),
                rounds_a=opt("rounds_a"),
                rounds_b=opt("rounds_b"),
            ))
    out.sort(key=lambda m: m.date)
    return out
