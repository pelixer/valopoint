"""Scrape the bracket of the most relevant ongoing event from vlr.gg.

Priority (user preference): international > Pacific > Americas > EMEA > China.

vlr.gg bracket pages list every match slot (with teams once known and the
winner once played) but not the links between slots, so the feeding rules
are filled in from the standard VCT formats:
  * GSL group (Opening x2 -> Winner's / Elimination -> Decider): group 1st =
    Winner's winner, 2nd = Decider winner;
  * 8-team double elimination playoffs (UQF x4, USF x2, UF, LR1 x2, LR2 x2,
    LSF, LF, GF), lower round 2 crossed to avoid rematches.
Real team names from vlr.gg always override these rules as soon as they appear.
Unknown formats fall back to the list of matches whose teams are already known.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from .vlr import Fetcher, _txt

PRIORITY = {"INTL": 0, "PAC": 1, "AMER": 2, "EMEA": 3, "CN": 4}


def pick_event(events: list[dict]) -> dict | None:
    """Most relevant event: ongoing/upcoming first, then by region priority, newest first."""
    if not events:
        return None
    def key(e):
        return (bool(e.get("complete")), PRIORITY.get(e.get("region"), 9), -int(e["event_id"]))
    return sorted(events, key=key)[0]


def parse_bracket_page(html: str) -> list[dict]:
    """[{side: upper|lower, cols: [{label, items: [{match_id, slug, teams: [(name|None, score, won)], ts}]}]}]"""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for cont in soup.select(".bracket-container"):
        side = "lower" if "mod-lower" in (cont.get("class") or []) else "upper"
        cols = []
        for col in cont.select(".bracket-col"):
            label = _txt(col.select_one(".bracket-col-label"))
            items = []
            for it in col.select(".bracket-item"):
                href = it.get("href") or ""
                m = re.match(r"^/(\d+)/(.*)$", href)
                if not m:
                    continue  # "Qualified" placeholder
                teams = []
                for t in it.select(".bracket-item-team")[:2]:
                    name = _txt(t.select_one(".bracket-item-team-name span")) or None
                    if name and name.upper() == "TBD":
                        name = None
                    score = _txt(t.select_one(".bracket-item-team-score"))
                    teams.append((name, score, "mod-winner" in (t.get("class") or [])))
                ts = it.select_one("[data-utc-ts]")
                items.append({"match_id": int(m.group(1)), "slug": m.group(2), "teams": teams,
                              "ts": ts.get("data-utc-ts") if ts else None})
            cols.append({"label": label, "items": items})
        out.append({"side": side, "cols": cols})
    return out


def stage_pages(f: Fetcher, event_id: int) -> list[str]:
    soup = BeautifulSoup(f.get(f"/event/{event_id}", refresh=True), "html.parser")
    paths = []
    for a in soup.select("a[href^='/event/']"):
        h = a.get("href", "")
        if re.match(rf"^/event/{event_id}/[^/?#]+/[^/?#]+$", h) and h not in paths:
            paths.append(h)
    return paths or [f"/event/{event_id}"]


def _iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except ValueError:
        return None


def _slot(item, idx):
    name = item["teams"][idx][0] if len(item["teams"]) > idx else None
    return name


def _winner(item):
    for name, _, won in item["teams"]:
        if won and name:
            return name
    return None


def build_bracket(event: dict, pages: dict[str, list[dict]]) -> dict:
    matches, results, assumed = [], {}, []
    groups: dict[str, dict] = {}
    playoff: dict[str, list] = {}
    pcols: dict[str, list[list]] = {"upper": [], "lower": []}   # playoff columns in page order

    def add(mid, a, b, rnd, item, bo=3):
        # vlr names win over feeding rules once both are known
        na, nb = _slot(item, 0), _slot(item, 1)
        if na and nb:
            a, b = na, nb
        if a is None or b is None:
            return False
        matches.append({"id": mid, "a": a, "b": b, "best_of": bo, "round": rnd,
                        "vlr_id": item["match_id"], "time": _iso(item["ts"])})
        w = _winner(item)
        if w:
            results[mid] = w
        return True

    for path, conts in pages.items():
        for cont in conts:
            for col in cont["cols"]:
                lab = col["label"].lower()
                if col["items"] and not any(k in lab for k in ("opening", "winner", "elimination", "decider")):
                    pcols[cont["side"]].append(col["items"])
                for i, it in enumerate(col["items"]):
                    g = re.search(r"-([a-h])$", it["slug"])
                    if any(k in lab for k in ("opening", "winner", "elimination", "decider")) and g:
                        role = ("O" + str(len(groups.setdefault(g.group(1).upper(), {}).get("O", [])) + 1)
                                if "opening" in lab else "W" if "winner" in lab else
                                "E" if "elimination" in lab else "D")
                        grp = groups.setdefault(g.group(1).upper(), {})
                        if role.startswith("O"):
                            grp.setdefault("O", []).append(it)
                        else:
                            grp[role] = it
                    else:
                        playoff.setdefault(lab, []).append(it)

    # GSL groups
    for G in sorted(groups):
        grp = groups[G]
        o = grp.get("O", [])
        if len(o) >= 2:
            add(f"{G}-O1", _slot(o[0], 0), _slot(o[0], 1), f"그룹 {G} 오프닝", o[0])
            add(f"{G}-O2", _slot(o[1], 0), _slot(o[1], 1), f"그룹 {G} 오프닝", o[1])
        if "W" in grp:
            add(f"{G}-W", f"W:{G}-O1", f"W:{G}-O2", f"그룹 {G} 승자전", grp["W"])
        if "E" in grp:
            add(f"{G}-E", f"L:{G}-O1", f"L:{G}-O2", f"그룹 {G} 패자전", grp["E"])
        if "D" in grp:
            add(f"{G}-D", f"L:{G}-W", f"W:{G}-E", f"그룹 {G} 최종전", grp["D"])

    def col(keys, exclude=("quarter", "semi")):
        for lab, items in playoff.items():
            if all(k in lab for k in keys) and not any(x in lab for x in exclude if x not in keys):
                return items
        return []

    uqf, usf = col(("upper", "quarter")), col(("upper", "semi"))
    uf, gf = col(("upper", "final")), col(("grand",))
    lr1, lr2 = col(("lower", "round 1")), col(("lower", "round 2"))
    lsf, lf = col(("lower", "semi")), col(("lower", "final"))
    # positional fallback: labels vary between events, column shapes do not
    up, lo = pcols["upper"], pcols["lower"]
    shape_u, shape_l = [len(c) for c in up], [len(c) for c in lo]
    if shape_u[:3] == [4, 2, 1] and shape_l == [2, 2, 1, 1] and (len(up) >= 4 or gf):
        uqf, usf, uf = up[0], up[1], up[2]
        gf = up[3] if len(up) >= 4 else gf
        lr1, lr2, lsf, lf = lo
    std8 = len(uqf) == 4 and len(usf) == 2 and uf and gf and len(lr1) == 2 and len(lr2) == 2 and lsf and lf
    if std8:
        G = sorted(groups)
        seed = []
        if len(G) == 4:  # assumed cross seeding until vlr fills the slots
            A, B, C, D = G
            seed = [(f"W:{A}-W", f"W:{B}-D"), (f"W:{B}-W", f"W:{A}-D"),
                    (f"W:{C}-W", f"W:{D}-D"), (f"W:{D}-W", f"W:{C}-D")]
        for i, it in enumerate(uqf):
            a, b = seed[i] if seed else (None, None)
            if add(f"UQF{i+1}", a, b, "상위 8강", it) and not (_slot(it, 0) and _slot(it, 1)):
                assumed.append(f"UQF{i+1}")
        add("USF1", "W:UQF1", "W:UQF2", "상위 4강", usf[0]); add("USF2", "W:UQF3", "W:UQF4", "상위 4강", usf[1])
        add("LR1-1", "L:UQF1", "L:UQF2", "하위 1R", lr1[0]); add("LR1-2", "L:UQF3", "L:UQF4", "하위 1R", lr1[1])
        add("UF", "W:USF1", "W:USF2", "상위 결승", uf[0])
        add("LR2-1", "L:USF2", "W:LR1-1", "하위 2R", lr2[0]); add("LR2-2", "L:USF1", "W:LR1-2", "하위 2R", lr2[1])
        add("LSF", "W:LR2-1", "W:LR2-2", "하위 4강", lsf[0])
        add("LF", "L:UF", "W:LSF", "하위 결승", lf[0], bo=5)
        add("GF", "W:UF", "W:LF", "결승", gf[0], bo=5)
        kind, final = "full", "GF"
    else:
        # unknown format: only matches whose two teams are already known
        for lab, items in playoff.items():
            for i, it in enumerate(items):
                add(f"P{it['match_id']}", None, None, lab.title(), it)
        kind, final = ("groups" if groups else "list"), (matches[-1]["id"] if matches else None)

    teams = sorted({m[s] for m in matches for s in ("a", "b") if not re.match(r"^[WL]:", m[s])})
    return {"id": f"vlr-{event['event_id']}", "event_id": event["event_id"], "name": event["name"],
            "region": event.get("region"), "kind": kind, "teams": teams, "matches": matches,
            "final": final, "results": results, "assumed": assumed}


VETO_RE = re.compile(r"(\S+)\s+(ban|pick)\s+([A-Za-z]+)|([A-Za-z]+)\s+remains", re.I)


def parse_veto(note: str) -> dict | None:
    """'PRX ban Abyss; TL ban Sunset; PRX pick Ascent; TL pick Haven; ...; Lotus remains'
    -> {"order": [maps in play order], "steps": [[tag, action, map], ...]}"""
    steps, picks, decider = [], [], None
    for part in note.split(";"):
        m = VETO_RE.search(part.strip())
        if not m:
            continue
        if m.group(4):
            decider = m.group(4).title()
            steps.append([None, "remains", decider])
        else:
            tag, act, mp = m.group(1), m.group(2).lower(), m.group(3).title()
            steps.append([tag, act, mp])
            if act == "pick":
                picks.append(mp)
    if not steps:
        return None
    return {"order": picks + ([decider] if decider else []), "steps": steps}


def resolve_teams(br: dict) -> dict[str, tuple]:
    """match id -> (team a, team b), W:/L: refs resolved from played results (None if unknown)."""
    res, out = {}, {}

    def known(ref):
        mm = re.match(r"^([WL]):(.+)$", ref or "")
        if mm:
            r = res.get(mm.group(2))
            return None if r is None else r[0 if mm.group(1) == "W" else 1]
        return ref

    for m in br["matches"]:
        a, b = known(m["a"]), known(m["b"])
        out[m["id"]] = (a, b)
        w = br.get("results", {}).get(m["id"])
        if a and b and w in (a, b):
            res[m["id"]] = (w, b if w == a else a)
    return out


def scrape_bracket(f: Fetcher, event: dict) -> dict:
    pages = {p: parse_bracket_page(f.get(p, refresh=True)) for p in stage_pages(f, event["event_id"])}
    br = build_bracket(event, pages)
    # actual veto (map order) for every match whose teams are known (refs resolved by results)
    teams = resolve_teams(br)
    for m in br["matches"]:
        if not all(teams.get(m["id"], (None, None))):
            continue
        try:
            soup = BeautifulSoup(f.get(f"/{m['vlr_id']}", refresh=m["id"] not in br["results"]), "html.parser")
        except Exception:
            continue
        note = _txt(soup.select_one(".match-header-note"))
        v = parse_veto(note) if note else None
        if v:
            m["veto"] = v
    return br
