from __future__ import annotations

import argparse

from .backtest import backtest
from .bracket import load_bracket, match_forecast, simulate
from .data import load_matches
from .rating import fit, power_table
from .synth import generate


def main(argv=None):
    ap = argparse.ArgumentParser(prog="valopoint")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synth", help="write synthetic sample CSV")
    s.add_argument("out")

    s = sub.add_parser("rank", help="power ranking")
    s.add_argument("csv")
    s.add_argument("--top", type=int, default=20)

    s = sub.add_parser("backtest", help="walk-forward evaluation")
    s.add_argument("csv")

    s = sub.add_parser("predict", help="single match forecast")
    s.add_argument("csv"); s.add_argument("team_a"); s.add_argument("team_b")
    s.add_argument("--bo", type=int, default=3)

    s = sub.add_parser("bracket", help="Monte Carlo bracket simulation")
    s.add_argument("csv"); s.add_argument("bracket_json")
    s.add_argument("--n", type=int, default=20000)

    a = ap.parse_args(argv)
    if a.cmd == "synth":
        generate(a.out); print("wrote", a.out); return

    ms = load_matches(a.csv)
    if a.cmd == "backtest":
        r = backtest(ms)
        print(f"INTL matches={r['n']} logloss={r['log_loss']:.4f} brier={r['brier']:.4f} acc={r['accuracy']:.3f}")
        return
    book = fit(ms)
    if a.cmd == "rank":
        print(f"{'#':>3} {'team':<18}{'region':<7}{'rating':>8}{'power':>7}")
        for i, (t, reg, s_, pw) in enumerate(power_table(book)[: a.top], 1):
            print(f"{i:>3} {t:<18}{reg:<7}{s_:>8.0f}{pw:>7.1f}")
        print("\nregion offsets:", {k: round(v) for k, v in sorted(book.region.items(), key=lambda x: -x[1])})
    elif a.cmd == "predict":
        f = match_forecast(book, a.team_a, a.team_b, a.bo)
        print(f"{a.team_a} vs {a.team_b}: map {f['map']:.1%}, Bo{a.bo} {f['series']:.1%}")
    elif a.cmd == "bracket":
        br = load_bracket(a.bracket_json)
        out = simulate(book, br, n=a.n)
        print(br.get("name", "bracket"))
        for t, p in sorted(out["champion"].items(), key=lambda x: -x[1]):
            print(f"  {t:<18}{p:>7.1%}")


if __name__ == "__main__":
    main()
