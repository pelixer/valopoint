import json
from datetime import datetime, timezone

from valopoint.ledger import locked_predictions, update
from valopoint.veto import VetoModel, recent_periods


def _model(theta_a=0.02):
    teams = [{"name": "A", "region": "PAC", "theta": {"Haven": theta_a, "Bind": theta_a, "Lotus": theta_a}},
             {"name": "B", "region": "PAC", "theta": {"Haven": 0.0, "Bind": 0.0, "Lotus": 0.0}}]
    return {"meta": {"generated_at": "2026-10-01T00:00:00+00:00"}, "calib": {"beta": 1.0},
            "regions": {"PAC": {"gamma": 0.0}}, "maps": ["Haven", "Bind", "Lotus"], "teams": teams}


def _brackets(results=None):
    return {"brackets": [{"id": "x", "results": results or {}, "matches": [
        {"id": "M1", "a": "A", "b": "B", "best_of": 3, "time": "2026-10-05T10:00:00+00:00"}]}]}


def test_ledger_append_only(tmp_path):
    mp, bp, lp = tmp_path / "m.json", tmp_path / "b.json", tmp_path / "l.json"
    mp.write_text(json.dumps(_model())); bp.write_text(json.dumps(_brackets()))
    t0 = datetime(2026, 10, 4, tzinfo=timezone.utc)
    assert update(mp, bp, lp, now=t0) == 1
    assert update(mp, bp, lp, now=t0) == 0            # unchanged -> nothing appended
    first = json.loads(lp.read_text())[0]
    mp.write_text(json.dumps(_model(0.05)))
    assert update(mp, bp, lp, now=datetime(2026, 10, 5, tzinfo=timezone.utc)) == 1
    led = json.loads(lp.read_text())
    assert led[0] == first and len(led) == 2           # earlier entry untouched
    # after the start time nothing more is recorded
    mp.write_text(json.dumps(_model(0.09)))
    assert update(mp, bp, lp, now=datetime(2026, 10, 5, 11, tzinfo=timezone.utc)) == 0
    locked = locked_predictions(led, _brackets({"M1": "A"})["brackets"])
    assert locked[0]["p"] == led[1]["p"] and locked[0]["correct"] == (led[1]["p"] > 0.5)


def test_veto_model_roundtrip():
    recs = [{"steps": [["A", "ban", "Bind"], ["B", "ban", "Haven"], ["A", "pick", "Lotus"],
                       ["B", "pick", "Split"], ["A", "ban", "Ascent"], ["B", "ban", "Sunset"], [None, "remains", "Abyss"]]}]
    vm = VetoModel(recs)
    pool = ["Bind", "Haven", "Lotus", "Split", "Ascent", "Sunset", "Abyss"]
    seqs = vm.sequences("A", "B", pool, 3)
    assert abs(sum(p for _, p in seqs) - 1) < 1e-3 and all(len(s) == 3 for s, _ in seqs)
    vm2 = VetoModel.from_json(vm.to_json(["A", "B"]))
    assert vm2.sequences("A", "B", pool, 3)[:5] == seqs[:5]
    assert vm.presence("A", "B", pool)["Bind"] < vm.presence("A", "B", pool)["Lotus"]


def test_recent_periods_groups_stages():
    ev = [{"event_id": 1, "tier": "league"}, {"event_id": 2, "tier": "league"},
          {"event_id": 3, "tier": "masters"}, {"event_id": 4, "tier": "league"}, {"event_id": 5, "tier": "champions"}]
    starts = {1: "2026-04-01", 2: "2026-04-05", 3: "2026-06-01", 4: "2026-07-15", 5: "2026-09-20"}
    assert recent_periods(ev, starts, 3, before="2026-09-20") == [[4], [3], [1, 2]]
