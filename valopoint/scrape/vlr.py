"""vlr.gg scraper (personal, non-commercial use).

Politeness: one request per `delay` seconds, every page cached on disk, so a
re-run only fetches pages not seen before (completed matches never change).

Collected granularity: one row per (match, map, player) with agent and stats.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.vlr.gg"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
CACHE = Path(os.environ.get("VALOPOINT_CACHE", "data/cache"))


class Fetcher:
    def __init__(self, delay: float = 1.5, cache: Path = CACHE, max_seconds: float = 60.0):
        self.delay = delay
        self.cache = cache
        self.max_seconds = max_seconds
        self.cache.mkdir(parents=True, exist_ok=True)
        self._last = 0.0
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def get(self, path: str, refresh: bool = False) -> str:
        url = path if path.startswith("http") else BASE + path
        f = self.cache / (hashlib.sha1(url.encode()).hexdigest() + ".html")
        if f.exists() and not refresh:
            return f.read_text(encoding="utf-8")
        last_err = None
        for attempt in range(4):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            t0 = time.time()
            try:
                text, status, headers = self._download(url)
            except (requests.RequestException, TimeoutError) as e:
                last_err = e
                print(f"    GET {url} -> {type(e).__name__}: {e}", flush=True)
                time.sleep(2 ** (attempt + 2))
                continue
            finally:
                self._last = time.time()
            print(f"    GET {url} -> {status} ({len(text)} B, {time.time() - t0:.1f}s)", flush=True)
            if status == 200:
                if "cf-mitigated" in headers or "<title>Just a moment" in text[:2000]:
                    raise RuntimeError(f"Cloudflare challenge blocked {url}")
                f.write_text(text, encoding="utf-8")
                return text
            last_err = RuntimeError(f"HTTP {status} for {url}")
            if status in (429, 500, 502, 503, 504):
                time.sleep(2 ** (attempt + 2))
                continue
            break
        raise last_err or RuntimeError(f"failed {url}")

    def _download(self, url: str) -> tuple[str, int, dict]:
        """GET with a hard total deadline (requests' timeout is per socket read)."""
        deadline = time.time() + self.max_seconds
        with self.s.get(url, timeout=(10, 20), stream=True) as r:
            chunks = []
            for chunk in r.iter_content(65536):
                chunks.append(chunk)
                if time.time() > deadline:
                    raise TimeoutError(f"download exceeded {self.max_seconds}s")
            r.encoding = r.encoding or "utf-8"
            return b"".join(chunks).decode(r.encoding, errors="replace"), r.status_code, dict(r.headers)


def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _num(s: str) -> float | None:
    s = s.strip().replace("%", "")
    if not s or s in ("-", "\xa0"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _stat(td) -> float | None:
    """vlr stat cells hold 'both / t / ct' spans; take the combined value."""
    both = td.select_one(".mod-both")
    return _num(_txt(both) if both else _txt(td))


# --------------------------------------------------------------- event pages

def event_match_ids(f: Fetcher, event_id: int) -> list[int]:
    html = f.get(f"/event/matches/{event_id}/?series_id=all", refresh=True)
    soup = BeautifulSoup(html, "html.parser")
    ids = []
    for a in soup.select("a.match-item, a.wf-module-item"):
        m = re.match(r"^/(\d+)/", a.get("href", ""))
        if m:
            ids.append(int(m.group(1)))
    return list(dict.fromkeys(ids))


def event_meta(f: Fetcher, event_id: int) -> dict:
    html = f.get(f"/event/{event_id}")
    soup = BeautifulSoup(html, "html.parser")
    title = _txt(soup.select_one(".wf-title")) or _txt(soup.title)
    return {"event_id": event_id, "event": title}


# --------------------------------------------------------------- match pages

@dataclass
class MapRow:
    match_id: int
    game_id: str
    event_id: int
    event: str
    stage: str
    date: str
    map: str
    map_order: int
    team: str
    opp: str
    team_rounds: int | None
    opp_rounds: int | None
    player: str
    player_id: int | None
    agent: str
    rating: float | None
    acs: float | None
    k: float | None
    d: float | None
    a: float | None
    kast: float | None
    adr: float | None
    hs: float | None
    fk: float | None
    fd: float | None
    best_of: int
    completed: bool


STAT_COLS = ["rating", "acs", "k", "d", "a", "kd_diff", "kast", "adr", "hs", "fk", "fd", "fk_diff"]


def parse_match(html: str, match_id: int, event_id: int, event: str) -> list[MapRow]:
    soup = BeautifulSoup(html, "html.parser")
    teams = [_txt(x) for x in soup.select(".match-header-link-name .wf-title-med")][:2]
    if len(teams) < 2:
        return []
    stage = _txt(soup.select_one(".match-header-event-series"))
    date_el = soup.select_one(".moment-tz-convert[data-utc-ts]")
    date = (date_el["data-utc-ts"][:10] if date_el else "")
    note = " ".join(_txt(x) for x in soup.select(".match-header-vs-note"))
    bo = re.search(r"Bo(\d)", note)
    best_of = int(bo.group(1)) if bo else 3
    completed = "final" in note.lower()

    rows: list[MapRow] = []
    order = 0
    for game in soup.select(".vm-stats-game"):
        gid = game.get("data-game-id", "")
        if not gid or gid == "all":
            continue
        header = game.select_one(".vm-stats-game-header")
        if header is None:
            continue
        mname = _txt(header.select_one(".map div span") or header.select_one(".map"))
        mname = re.sub(r"\s*(PICK|Pick)\s*$", "", mname).split()[0] if mname else ""
        scores = [_num(_txt(s)) for s in header.select(".score")]
        if len(scores) < 2 or scores[0] is None:
            continue
        order += 1
        tables = game.select("table.wf-table-inset.mod-overview")
        for ti, tbl in enumerate(tables[:2]):
            team, opp = teams[ti], teams[1 - ti]
            tr_, or_ = (scores[0], scores[1]) if ti == 0 else (scores[1], scores[0])
            for tr in tbl.select("tbody tr"):
                pcell = tr.select_one("td.mod-player")
                if pcell is None:
                    continue
                name = _txt(pcell.select_one(".text-of")) or _txt(pcell).split()[0]
                link = pcell.select_one("a")
                pid = None
                if link and (mm := re.match(r"^/player/(\d+)/", link.get("href", ""))):
                    pid = int(mm.group(1))
                img = tr.select_one("td.mod-agents img")
                agent = (img.get("title") or img.get("alt") or "").strip().lower() if img else ""
                vals = [_stat(td) for td in tr.select("td.mod-stat")]
                vals += [None] * (len(STAT_COLS) - len(vals))
                v = dict(zip(STAT_COLS, vals))
                rows.append(MapRow(
                    match_id=match_id, game_id=gid, event_id=event_id, event=event,
                    stage=stage, date=date, map=mname, map_order=order,
                    team=team, opp=opp,
                    team_rounds=int(tr_) if tr_ is not None else None,
                    opp_rounds=int(or_) if or_ is not None else None,
                    player=name, player_id=pid, agent=agent,
                    rating=v["rating"], acs=v["acs"], k=v["k"], d=v["d"], a=v["a"],
                    kast=v["kast"], adr=v["adr"], hs=v["hs"], fk=v["fk"], fd=v["fd"],
                    best_of=best_of, completed=completed,
                ))
    return rows


def scrape_event(f: Fetcher, event_id: int, log=print) -> tuple[list[dict], bool]:
    """Returns (rows, complete). complete = every listed match is finished."""
    meta = event_meta(f, event_id)
    ids = event_match_ids(f, event_id)
    log(f"  {meta['event']}: {len(ids)} matches")
    out: list[dict] = []
    complete = bool(ids)
    for i, mid in enumerate(ids, 1):
        try:
            html = f.get(f"/{mid}")
        except Exception as e:  # one bad page must not kill the whole event
            log(f"  [{i}/{len(ids)}] match {mid}: FAILED {e}")
            complete = False
            continue
        rows = parse_match(html, mid, event_id, meta["event"])
        if not rows or not rows[0].completed:
            complete = False
        if rows and not rows[0].completed:
            # unfinished/live match: drop cache so the next run refetches it
            f.cache.joinpath(hashlib.sha1(f"{BASE}/{mid}".encode()).hexdigest() + ".html").unlink(missing_ok=True)
            rows = [r for r in rows if r.team_rounds is not None and max(r.team_rounds, r.opp_rounds or 0) >= 13]
        out.extend(asdict(r) for r in rows)
        log(f"  [{i}/{len(ids)}] match {mid}: {len(rows)} rows")
    return out, complete
