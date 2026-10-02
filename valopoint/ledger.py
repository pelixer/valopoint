"""Append-only prediction ledger.

Before each match, the prediction the app is showing is written down with a
timestamp and never edited afterwards (new snapshots are appended only when the
numbers change). After the match, the last snapshot recorded before its start
time is THE pre-match prediction — no recomputation, no hindsight. Git history
of web/public/data/ledger.json is the audit trail.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .model import logit, sigmoid, win_prob_from_q
from .predict import series_prob_ordered, veto_maps


class Snapshot:
    """Predictions from an exported model.json (same maths as the web engine)."""

    def __init__(self, model: dict):
        self.m = model
        self.teams = {t["name"]: t for t in model["teams"]}
        self.beta = model.get("calib", {}).get("beta", 1.0)
        self.gamma = {r: v.get("gamma", 0.0) for r, v in model.get("regions", {}).items()}
        self.veto = None
        if model.get("veto_model"):
            from .veto import VetoModel
            self.veto = VetoModel.from_json(model["veto_model"])

    def map_prob(self, a, b, mp):
        A, B = self.teams.get(a), self.teams.get(b)
        if not A or not B:
            return 0.5
        dS = A["theta"].get(mp, 0.0) - B["theta"].get(mp, 0.0)
        z = self.beta * logit(win_prob_from_q(0.5 + dS)) + self.gamma.get(A["region"], 0) - self.gamma.get(B["region"], 0)
        return float(sigmoid(z))

    def series(self, a, b, best_of, order=None):
        if order:
            ps = [self.map_prob(a, b, mp) for mp in order]
            return series_prob_ordered(ps), "veto", [{"map": mp, "p": round(p, 4)} for mp, p in zip(order, ps)]
        pool = self.m["maps"]
        pmap = {mp: self.map_prob(a, b, mp) for mp in pool}
        if self.veto:
            seqs = self.veto.sequences(a, b, pool, best_of)
            p = sum(pr * series_prob_ordered([pmap[x] for x in seq]) for seq, pr in seqs) / max(sum(pr for _, pr in seqs), 1e-9)
            pres = self.veto.presence(a, b, pool, best_of)
            maps = [{"map": mp, "p": round(pmap[mp], 4), "presence": round(pres.get(mp, 0), 3)} for mp in pool]
            return float(p), "veto_model", maps
        ps = [series_prob_ordered([pmap[x] for x in veto_maps(pmap, best_of, af)]) for af in (True, False)]
        return float(np.mean(ps)), "greedy", [{"map": mp, "p": round(pmap[mp], 4)} for mp in pool]


def resolve(br: dict) -> dict:
    from .scrape.bracket import resolve_teams
    return resolve_teams(br)


def update(model_path="web/public/data/model.json", brackets_path="web/public/data/brackets.json",
           ledger_path="web/public/data/ledger.json", now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    brs = json.loads(Path(brackets_path).read_text(encoding="utf-8")).get("brackets", [])
    lp = Path(ledger_path)
    ledger = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else []
    last = {}
    for e in ledger:
        last[(e["bracket"], e["match"])] = e
    snap = Snapshot(model)
    added = 0
    for br in brs:
        teams = resolve(br)
        for m in br["matches"]:
            if m["id"] in br.get("results", {}):
                continue
            a, b = teams[m["id"]]
            if not a or not b:
                continue
            start = datetime.fromisoformat(m["time"]) if m.get("time") else None
            if start and start <= now:
                continue  # already started: too late to record a pre-match prediction
            order = (m.get("veto") or {}).get("order")
            p, basis, maps = snap.series(a, b, m.get("best_of", 3), order)
            prev = last.get((br["id"], m["id"]))
            if prev and prev["team_a"] == a and prev["team_b"] == b and abs(prev["p"] - p) < 0.0005 and prev["basis"] == basis:
                continue
            entry = {"recorded_at": now.isoformat(timespec="seconds"), "bracket": br["id"], "match": m["id"],
                     "vlr_id": m.get("vlr_id"), "match_time": m.get("time"), "team_a": a, "team_b": b,
                     "best_of": m.get("best_of", 3), "p": round(p, 4), "basis": basis, "maps": maps,
                     "model_generated_at": model["meta"]["generated_at"]}
            ledger.append(entry)       # append only — earlier entries are never modified
            last[(br["id"], m["id"])] = entry
            added += 1
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text(json.dumps(ledger, ensure_ascii=False, indent=0), encoding="utf-8")
    return added


def locked_predictions(ledger: list[dict], brackets: list[dict]) -> list[dict]:
    """For finished matches: the last snapshot recorded before the match start, with the result."""
    out = []
    for br in brackets:
        for m in br["matches"]:
            w = br.get("results", {}).get(m["id"])
            if not w:
                continue
            snaps = [e for e in ledger if e["bracket"] == br["id"] and e["match"] == m["id"]
                     and (not m.get("time") or e["recorded_at"] < m["time"])]
            if snaps:
                e = snaps[-1]
                out.append({**e, "winner": w, "correct": (e["p"] > 0.5) == (w == e["team_a"])})
    return out
