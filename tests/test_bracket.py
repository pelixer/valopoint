"""Bracket scraper against the vlr.gg Champions 2026 bracket markup (structure from a live page)."""
from valopoint.scrape.bracket import build_bracket, parse_bracket_page, pick_event


def _item(mid, slug, t1=None, t2=None, s1="", s2="", win=None):
    def team(n, s, first):
        cls = "bracket-item-team" + (" mod-first" if first else "") + (" mod-winner" if win and win == n else "")
        return (f'<div class="{cls}"><div class="bracket-item-team-name"><img src="x.png"/><span>{n or ""}</span></div>'
                f'<div class="bracket-item-team-score"> {s} </div></div>')
    return (f'<div class="bracket-row"><a class="bracket-item" href="/{mid}/{slug}" title="">'
            + team(t1, s1, True) + team(t2, s2, False)
            + '<div class="bracket-item-status moment-tz-convert" data-utc-ts="1790499600"></div></a></div>')


def _col(label, items):
    return f'<div class="bracket-col"><div class="bracket-col-label"> {label} </div>{"".join(items)}</div>'


def _cont(side, cols):
    return f'<div class="bracket-container mod-{side}">{"".join(cols)}</div>'


GROUPS = {"a": ("100 Thieves", "T1", "JD Gaming", "FUT Esports"), "b": ("Global Esports", "Team Vitality", "EDward Gaming", "LOUD"),
          "c": ("G2 Esports", "TYLOO", "Paper Rex", "Team Liquid"), "d": ("Karmine Corp", "Xi Lai Gaming", "NRG", "Nongshim RedForce")}


def _group_html():
    html, mid = "", 1000
    for g, (t1, t2, t3, t4) in GROUPS.items():
        mid += 10
        up = _cont("upper", [
            _col("Opening", [_item(mid, f"x-opening-{g}", t1, t2, 2, 0, t1), _item(mid + 1, f"x-opening-{g}", t3, t4, 0, 2, t4)]),
            _col("Winner's", [_item(mid + 2, f"x-winners-{g}", t1, t4, 2, 1, t1)]),
            '<div class="bracket-col"><div class="bracket-col-label"> Qualified </div><span class="bracket-item mod-single"></span></div>'])
        lo = _cont("lower", [
            _col("Elimination", [_item(mid + 3, f"x-elimination-{g}", t2, t3)]),
            _col("Decider", [_item(mid + 4, f"x-decider-{g}")])])
        html += up + lo
    return html


def _playoff_html():
    u = _cont("upper", [
        _col("Upper Quarterfinals", [_item(2000 + i, "tbd-ubqf") for i in range(4)]),
        _col("Upper Semifinals", [_item(2010 + i, "tbd-ubsf") for i in range(2)]),
        _col("Upper Final", [_item(2020, "tbd-ubf")]), _col("Grand Final", [_item(2021, "tbd-gf")])])
    lo = _cont("lower", [
        _col("Lower Round 1", [_item(2030 + i, "tbd-lbr1") for i in range(2)]),
        _col("Lower Round 2", [_item(2040 + i, "tbd-lbr2") for i in range(2)]),
        _col("Lower Semifinal", [_item(2050, "tbd-lbsf")]), _col("Lower Final", [_item(2051, "tbd-lbf")])])
    return u + lo


def _resolve(ref, res):
    if ref.startswith(("W:", "L:")):
        r = res.get(ref[2:])
        return None if r is None else r[0 if ref[0] == "W" else 1]
    return ref


def test_champions_bracket():
    pages = {"/g": parse_bracket_page(_group_html()), "/p": parse_bracket_page(_playoff_html())}
    br = build_bracket({"event_id": 2766, "name": "Valorant Champions 2026", "region": "INTL"}, pages)
    assert br["kind"] == "full" and len(br["matches"]) == 34 and br["final"] == "GF"   # 4x5 group + 14 playoff
    ids = [m["id"] for m in br["matches"]]
    assert ids[:5] == ["A-O1", "A-O2", "A-W", "A-E", "A-D"] and ids[-1] == "GF"
    assert set(br["assumed"]) == {"UQF1", "UQF2", "UQF3", "UQF4"}
    assert br["results"]["A-O1"] == "100 Thieves" and br["results"]["A-W"] == "100 Thieves"
    m = {x["id"]: x for x in br["matches"]}
    assert (m["A-W"]["a"], m["A-W"]["b"]) == ("100 Thieves", "FUT Esports")       # names from vlr win
    assert (m["A-D"]["a"], m["A-D"]["b"]) == ("L:A-W", "W:A-E")                    # rule until known
    assert (m["UQF1"]["a"], m["UQF1"]["b"]) == ("W:A-W", "W:B-D")
    assert m["GF"]["best_of"] == 5 and m["LF"]["best_of"] == 5 and m["UF"]["best_of"] == 3
    # every reference points to an earlier match (valid execution order)
    seen = set()
    for x in br["matches"]:
        for s in ("a", "b"):
            if x[s][:2] in ("W:", "L:"):
                assert x[s][2:] in seen, (x["id"], x[s])
        seen.add(x["id"])
    # with results locked, refs resolve to the actual teams
    res = {}
    for x in br["matches"]:
        a, b = _resolve(x["a"], res), _resolve(x["b"], res)
        w = br["results"].get(x["id"])
        if a and b and w in (a, b):
            res[x["id"]] = (w, b if w == a else a)
    assert _resolve("L:A-W", res) == "FUT Esports"


def test_pick_event_priority():
    ev = [{"event_id": 1, "region": "CN", "complete": False}, {"event_id": 2, "region": "PAC", "complete": False},
          {"event_id": 3, "region": "INTL", "complete": True}, {"event_id": 4, "region": "AMER", "complete": False}]
    assert pick_event(ev)["event_id"] == 2
    ev.append({"event_id": 5, "region": "INTL", "complete": False})
    assert pick_event(ev)["event_id"] == 5
