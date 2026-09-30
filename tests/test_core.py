import json

import numpy as np
import pytest

from valopoint.backtest import elo_baseline, metrics, walk_forward
from valopoint.dataset import load
from valopoint.export import build
from valopoint.model import fit, win_prob_from_q
from valopoint.predict import series_prob_ordered, veto_maps
from valopoint.synth import generate


@pytest.fixture(scope="module")
def syn(tmp_path_factory):
    d = tmp_path_factory.mktemp("syn")
    truth = generate(d)
    return d, load(d), truth


def test_map_and_series_math():
    assert win_prob_from_q(0.5) == pytest.approx(0.5)
    assert win_prob_from_q(0.55) > 0.6
    assert series_prob_ordered([0.5, 0.5, 0.5]) == pytest.approx(0.5)
    assert series_prob_ordered([0.6] * 3) == pytest.approx(0.648)
    assert series_prob_ordered([0.6] * 5) > series_prob_ordered([0.6] * 3)


def test_veto_order():
    pm = {"a": .9, "b": .8, "c": .7, "d": .5, "e": .3, "f": .2, "g": .1}
    maps = veto_maps(pm, 3, a_first=True)
    # A bans g, B bans a, A picks b, B picks f, A bans e, B bans c -> decider d
    assert maps == ["b", "f", "d"]
    assert len(veto_maps(pm, 1)) == 1 and len(veto_maps(pm, 5)) == 5


def test_recovers_hidden_truth(syn):
    _, df, truth = syn
    m = fit(df)
    pl = m.player.assign(theta=lambda x: x["u"] + x["region"].map(m.region))
    true = pl.index.map(truth["player"]).astype(float)
    assert np.corrcoef(pl["theta"], true)[0, 1] > 0.9
    assert m.region["CN"] == min(m.region.values())       # weakest hidden region
    pa = m.p_agent.assign(t=(m.p_agent["pkey"] + "|" + m.p_agent["agent"]).map(truth["player_agent"]))
    assert pa[["dev", "t"]].corr().iloc[0, 1] > 0.4


def test_backtest_beats_baselines(syn):
    _, df, _ = syn
    rec, _ = walk_forward(df, since="2025-06-01")
    mm, me = metrics(rec), metrics(elo_baseline(df, since="2025-06-01"))
    assert mm["n"] > 100
    assert mm["log_loss"] < 0.69 and mm["log_loss"] < me["log_loss"]


def test_export_json(syn):
    d, df, _ = syn
    j = build(df, source="synthetic", brackets_dir=d / "brackets", log=lambda *_: None)
    json.dumps(j)
    assert j["teams"] and j["players"] and j["brackets"][0]["teams"]
    t = j["teams"][0]
    assert set(t["theta"]) == set(j["maps"]) and all(r in j["players"] for r in t["roster"])
