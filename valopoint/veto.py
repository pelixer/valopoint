"""Map veto model from recent veto history.

Window (user rule): only the two most recent completed event PERIODS before
the reference time, plus the event in progress. Rosters change every season and
the meta every few months, so older vetoes are not used. A period groups events
that run side by side (the four regional leagues of one stage = one period).

Each team's ban / pick tendencies are counts over that window, shrunk toward the
league-wide tendency, and the VCT veto order is enumerated exactly:
  Bo3: A ban, B ban, A pick, B pick, A ban, B ban, decider
  Bo5: A ban, B ban, A pick, B pick, A pick, B pick, decider
  Bo1: six alternating bans, decider
Who bans first is not known in advance, so both orders are averaged.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

ORDER = {1: "ABABAB", 3: "ABabAB", 5: "ABabab"}   # upper = ban, lower = pick


def _stage_key(e: dict):
    """Regional events of the same split share a key (e.g. ('2026', 'stage 2'))."""
    m = re.search(r"(kickoff|stage\s*\d)", e.get("name", ""), re.I)
    y = re.search(r"20\d\d", e.get("name", ""))
    return (y.group(0) if y else str(e.get("year", "")), re.sub(r"\s+", " ", m.group(1).lower())) if m else None


def recent_periods(events: list[dict], starts: dict, n: int, before=None, gap_days: int = 21) -> list[list[int]]:
    """Most recent `n` event periods (each a list of event ids) starting before `before`.

    A period is one international event, or the regional leagues of one split
    (same "Stage N"/"Kickoff" name; events without such a name are grouped when they
    start within `gap_days` of each other)."""
    rows = sorted(((pd.Timestamp(starts[e["event_id"]]), e) for e in events if e["event_id"] in starts),
                  key=lambda x: x[0])
    if before is not None:
        rows = [r for r in rows if r[0] < pd.Timestamp(before)]
    periods: list[dict] = []
    for start, e in rows:
        intl = e.get("tier", "league") in ("masters", "champions")
        key = None if intl else _stage_key(e)
        hit = None
        if not intl:
            for p in periods[::-1]:
                if p["intl"]:
                    continue
                if (key and p["key"] == key) or (not key and not p["key"] and (start - p["start"]).days <= gap_days):
                    hit = p
                break
        if hit:
            hit["ids"].append(e["event_id"])
        else:
            periods.append({"start": start, "intl": intl, "key": key, "ids": [e["event_id"]]})
    return [p["ids"] for p in periods[::-1][:n]]


def load_vetoes(data_dir: str | Path, event_ids) -> list[dict]:
    out = []
    for eid in event_ids:
        p = Path(data_dir) / "veto" / f"{eid}.json"
        if p.exists():
            out.extend(json.loads(p.read_text(encoding="utf-8")))
    return out


class VetoModel:
    def __init__(self, records: list[dict], prior: float = 3.0):
        self.prior = prior
        self.ban = defaultdict(lambda: defaultdict(float))
        self.pick = defaultdict(lambda: defaultdict(float))
        self.g_ban = defaultdict(float)
        self.g_pick = defaultdict(float)
        self.n = len(records)
        for r in records:
            for team, act, mp in r["steps"]:
                if act == "ban":
                    self.ban[team][mp] += 1; self.g_ban[mp] += 1
                elif act == "pick":
                    self.pick[team][mp] += 1; self.g_pick[mp] += 1

    def _weights(self, team, act, left):
        own, glob = (self.ban, self.g_ban) if act == "ban" else (self.pick, self.g_pick)
        gtot = sum(glob[m] for m in left) or 1.0
        return {m: own[team][m] + self.prior * (glob[m] + 0.5) / (gtot + 0.5 * len(left)) for m in left}

    def sequences(self, a: str, b: str, pool: list[str], best_of: int = 3) -> list[tuple[tuple, float]]:
        """[(maps in play order, probability)], averaged over who bans first."""
        order = ORDER.get(best_of, ORDER[3])
        acc: dict[tuple, float] = defaultdict(float)

        def rec(i, left, picks, pr, first, second):
            if pr < 1e-6:
                return
            if i == len(order) or len(left) <= 1:
                acc[tuple(picks + left[:1])] += pr
                return
            ch = order[i]
            team = first if ch.upper() == "A" else second
            act = "ban" if ch.isupper() else "pick"
            w = self._weights(team, act, left)
            tot = sum(w.values())
            for m in left:
                rest = [x for x in left if x != m]
                rec(i + 1, rest, picks + [m] if act == "pick" else picks, pr * w[m] / tot, first, second)

        for first, second in ((a, b), (b, a)):
            rec(0, list(pool), [], 0.5, first, second)
        return sorted(acc.items(), key=lambda x: -x[1])

    def presence(self, a, b, pool, best_of=3) -> dict[str, float]:
        """P(map is played at all) — for display; deciders count even if the series ends early."""
        out = defaultdict(float)
        for seq, pr in self.sequences(a, b, pool, best_of):
            for m in seq:
                out[m] += pr
        return dict(out)

    @classmethod
    def from_json(cls, d: dict) -> "VetoModel":
        vm = cls([], prior=d.get("prior", 3.0))
        vm.n = d.get("n", 0)
        vm.g_ban.update(d.get("g_ban", {}))
        vm.g_pick.update(d.get("g_pick", {}))
        for t, c in d.get("ban", {}).items():
            vm.ban[t].update(c)
        for t, c in d.get("pick", {}).items():
            vm.pick[t].update(c)
        return vm

    def to_json(self, teams: list[str]) -> dict:
        return {"prior": self.prior, "n": self.n,
                "g_ban": dict(self.g_ban), "g_pick": dict(self.g_pick),
                "ban": {t: dict(self.ban[t]) for t in teams if t in self.ban},
                "pick": {t: dict(self.pick[t]) for t in teams if t in self.pick}}
