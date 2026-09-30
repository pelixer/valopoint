import pytest
from valopoint.series import series_win_prob
from valopoint.synth import generate
from valopoint.data import load_matches
from valopoint.rating import fit, power_table
from valopoint.backtest import backtest
from valopoint.bracket import load_bracket, simulate


def test_series_math():
    assert series_win_prob(0.5, 3) == pytest.approx(0.5)
    assert series_win_prob(0.6, 3) == pytest.approx(0.648)
    assert series_win_prob(0.6, 5) > series_win_prob(0.6, 3)


@pytest.fixture(scope="module")
def ms(tmp_path_factory):
    p = tmp_path_factory.mktemp("d") / "s.csv"
    generate(str(p))
    return load_matches(str(p))


def test_region_offsets_recovered(ms):
    b = fit(ms)
    assert b.region["PAC"] > b.region["CN"]  # true offsets +60 vs -60


def test_backtest_beats_coin_flip(ms):
    r = backtest(ms, warmup=30)
    assert r["n"] > 20 and r["log_loss"] < 0.6931


def test_bracket_probs_sum_to_one(ms):
    b = fit(ms)
    out = simulate(b, load_bracket("examples/masters_8team_double_elim.json"), n=2000)
    assert sum(out["champion"].values()) == pytest.approx(1.0)
