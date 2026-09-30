"""Map-level player dataset: one row per (game, player).

Source files:
  data/events.json         event list with region/tier (see scrape/events.py)
  data/rows/<event_id>.csv parsed player-map rows (see scrape/vlr.py MapRow)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .agents import role_of

# per-round outcome features used for the power point (Rating/ACS are excluded:
# they are fixed composites of the same inputs and would double count)
FEATURES = ["kpr", "dpr", "apr", "fkpr", "fdpr", "adr", "kast"]


def load(data_dir: str | Path = "data") -> pd.DataFrame:
    d = Path(data_dir)
    events = {e["event_id"]: e for e in json.loads((d / "events.json").read_text(encoding="utf-8"))}
    frames = [pd.read_csv(p) for p in sorted((d / "rows").glob("*.csv"))]
    if not frames:
        raise FileNotFoundError(f"no row files in {d/'rows'}")
    df = pd.concat(frames, ignore_index=True)
    df["region_ev"] = df["event_id"].map(lambda e: events.get(e, {}).get("region", ""))
    df["tier"] = df["event_id"].map(lambda e: events.get(e, {}).get("tier", "league"))
    return prepare(df)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["team_rounds"].notna() & df["opp_rounds"].notna()]
    df["R"] = df["team_rounds"] + df["opp_rounds"]
    df = df[df["R"] > 0]
    df["date"] = pd.to_datetime(df["date"])
    for s, c in [("kpr", "k"), ("dpr", "d"), ("apr", "a"), ("fkpr", "fk"), ("fdpr", "fd")]:
        df[s] = df[c] / df["R"]
    df["kast"] = df["kast"] / 100.0
    df["agent"] = df["agent"].fillna("").str.lower()
    df["role"] = df["agent"].map(role_of)
    df["pkey"] = np.where(df["player_id"].notna(), df["player_id"].astype("Int64").astype(str), df["player"])
    df["intl"] = df["tier"].isin(["masters", "champions"])
    df["team_region"] = team_regions(df)
    df = df.dropna(subset=FEATURES)
    # a map must have exactly 5 players per side to be usable
    n = df.groupby(["game_id", "team"])["pkey"].transform("size")
    return df[n == 5].reset_index(drop=True)


def team_regions(df: pd.DataFrame) -> pd.Series:
    """Home region of each team = most frequent region among its domestic events."""
    dom = df[~df["tier"].isin(["masters", "champions"]) & (df["region_ev"] != "")]
    home = dom.groupby("team")["region_ev"].agg(lambda s: s.mode().iat[0]).to_dict()
    return df["team"].map(home).fillna("UNK")


def games(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team) side with outcome."""
    g = df.groupby(["game_id", "team"], as_index=False).agg(
        opp=("opp", "first"), date=("date", "first"), map=("map", "first"),
        event_id=("event_id", "first"), match_id=("match_id", "first"),
        map_order=("map_order", "first"), best_of=("best_of", "first"),
        team_rounds=("team_rounds", "first"), opp_rounds=("opp_rounds", "first"),
        team_region=("team_region", "first"), intl=("intl", "first"),
    )
    g["win"] = (g["team_rounds"] > g["opp_rounds"]).astype(float)
    return g
