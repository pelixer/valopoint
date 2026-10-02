"""Round-level and situational data from vlr.gg match pages.

* overview tab (already fetched for player rows, so it comes from the page cache):
    - round rows: winner, winning side (attack / defense), how (elim / defuse / boom / time)
    - attack / defense split of each player's stats
* performance tab: multi-kills (2K-5K), clutches won (1v1-1v5), plants, defuses
* economy tab: pistol rounds won, buy type counts and wins (eco / $ / $$ / $$$)
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .vlr import OVW_COLS, Fetcher, _num, _player_identity, _txt

ADV_COLS = ["m2k", "m3k", "m4k", "m5k", "c1v1", "c1v2", "c1v3", "c1v4", "c1v5", "econ", "plants", "defuses"]
ECON_COLS = ["pistol_won", "eco", "eco_won", "semi_eco", "semi_eco_won", "semi_buy", "semi_buy_won", "full_buy", "full_buy_won"]


def _games(soup):
    return [g for g in soup.select(".vm-stats-game") if g.get("data-game-id") not in (None, "", "all")]


def _header_teams(soup) -> list[str]:
    return [_txt(x) for x in soup.select(".match-header-link-name .wf-title-med")][:2]


def _tag_team(game, teams) -> dict[str, str]:
    tags = [t for t in dict.fromkeys(_txt(t) for t in game.select(".ovw-row .ovw-player-tag")) if t]
    return {tags[0]: teams[0], tags[1]: teams[1]} if len(tags) == 2 and len(teams) == 2 else {}


def _own_text(el) -> str:
    """Text of an element without its popup contents."""
    if el is None:
        return ""
    return " ".join(s.strip() for s in el.find_all(string=True, recursive=False) if s.strip())


def parse_overview_extras(html: str, match_id: int) -> tuple[list[dict], list[dict]]:
    """(rounds, side_stats) from the overview page."""
    soup = BeautifulSoup(html, "html.parser")
    teams = _header_teams(soup)
    rounds, sides = [], []
    for game in _games(soup):
        gid = game["data-game-id"]
        tag_team = _tag_team(game, teams)
        rr = game.select_one(".vlr-rounds")
        if rr is not None and len(teams) == 2:
            cols = rr.select(".vlr-rounds-row-col")
            order = teams
            if cols:
                head_tags = [_txt(t) for t in cols[0].select(".team")]
                if len(head_tags) == 2 and all(t in tag_team for t in head_tags):
                    order = [tag_team[t] for t in head_tags]
            for c in cols[1:]:
                num = _num(_txt(c.select_one(".rnd-num")))
                sq = c.select(".rnd-sq")
                if num is None or len(sq) != 2:
                    continue
                win = [i for i, s in enumerate(sq) if "mod-win" in (s.get("class") or [])]
                if not win:
                    continue
                w = win[0]
                cls = sq[w].get("class") or []
                img = sq[w].select_one("img")
                how = re.sub(r"\.\w+$", "", img["src"].rsplit("/", 1)[-1]) if img and img.get("src") else ""
                rounds.append({"match_id": match_id, "game_id": gid, "round": int(num),
                               "winner": order[w], "loser": order[1 - w],
                               "win_side": "atk" if "mod-t" in cls else "def" if "mod-ct" in cls else "",
                               "how": how})
        for r in game.select(".ovw-row"):
            if "mod-head" in (r.get("class") or []) or not r.select_one(".mod-player"):
                continue
            name, pid, agent, tag = _player_identity(r.select_one(".mod-player"))
            row = {"match_id": match_id, "game_id": gid, "player": name, "player_id": pid,
                   "tag": tag, "team": tag_team.get(tag, tag)}
            for el in r.select("[data-col]"):
                key = OVW_COLS.get(el.get("data-col"))
                if not key or f"{key}_atk" in row:
                    continue
                t, ct = el.select_one(".mod-t"), el.select_one(".mod-ct")
                row[f"{key}_atk"] = _num(_txt(t)) if t else None
                row[f"{key}_def"] = _num(_txt(ct)) if ct else None
            sides.append(row)
    return rounds, sides


def parse_performance(html: str, match_id: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for game in _games(soup):
        t = game.select_one("table.mod-adv-stats")
        if t is None:
            continue
        for tr in t.select("tr")[1:]:
            tds = tr.select("td")
            if len(tds) < 2 + len(ADV_COLS):
                continue
            team_div = tds[0].select_one(".team")
            tag = _txt(tds[0].select_one(".team-tag"))
            name = _own_text(team_div.select_one("div")) if team_div and team_div.select_one("div") else ""
            img = tds[1].select_one("img")
            agent = re.sub(r"\.\w+$", "", img["src"].rsplit("/", 1)[-1]) if img and img.get("src") else ""
            row = {"match_id": match_id, "game_id": game["data-game-id"], "player": name, "tag": tag, "agent": agent}
            for k, td in zip(ADV_COLS, tds[2:]):
                v = _num(_own_text(td.select_one(".stats-sq")))
                row[k] = v if v is not None else 0.0
            out.append(row)
    return out


def parse_economy(html: str, match_id: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for game in _games(soup):
        t = game.select_one("table.mod-econ")
        if t is None or not t.select("th"):
            continue
        for tr in t.select("tr")[1:]:
            tds = tr.select("td")
            if len(tds) < 6:
                continue
            row = {"match_id": match_id, "game_id": game["data-game-id"], "tag": _txt(tds[0])}
            vals = []
            for td in tds[1:6]:
                nums = [float(x) for x in re.findall(r"\d+", _txt(td))]
                vals.append(nums)
            row["pistol_won"] = vals[0][0] if vals[0] else None
            for key, v in zip(["eco", "semi_eco", "semi_buy", "full_buy"], vals[1:]):
                row[key] = v[0] if v else None
                row[f"{key}_won"] = v[1] if len(v) > 1 else None
            out.append(row)
    return out


def scrape_match_extras(f: Fetcher, match_id: int) -> dict[str, list[dict]]:
    """All extras of one finished match; team tags resolved to team names."""
    rounds, sides = parse_overview_extras(f.get(f"/{match_id}"), match_id)
    tag_team = {r["tag"]: r["team"] for r in sides if r.get("tag")}
    adv = parse_performance(f.get(f"/{match_id}/?game=all&tab=performance", store=False), match_id)
    econ = parse_economy(f.get(f"/{match_id}/?game=all&tab=economy", store=False), match_id)
    for r in adv + econ:
        r["team"] = tag_team.get(r["tag"], r["tag"])
    return {"rounds": rounds, "sides": sides, "adv": adv, "econ": econ}
