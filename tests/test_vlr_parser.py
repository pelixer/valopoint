"""Parser test against vlr.gg's 2026 div-based match layout (structure copied from a live page)."""
from valopoint.scrape.vlr import parse_match


def _row(name, pid, tag, agent, k, d, a):
    def cell(col, v):
        return (f'<div class="ovw-cell" data-col="{col}"><span class="stats-sq">'
                f'<span class="side mod-both">{v}</span><span class="side mod-t">0</span>'
                f'<span class="side mod-ct">0</span></span></div>')
    def kda(col, v):
        return (f'<span class="ovw-kda-stat" data-col="{col}"><span class="side mod-both">{v}</span>'
                f'<span class="side mod-t">0</span><span class="side mod-ct">0</span></span>')
    return (
        '<div class="ovw-row"><div class="ovw-cell mod-player"><div class="ovw-player">'
        f'<i class="flag mod-ru" title="Russia"></i><a href="/player/{pid}/{name}">'
        f'<div class="ovw-player-name text-of">{name}</div><div class="ovw-player-tag ge-text-light">{tag}</div></a></div>'
        f'<div class="ovw-agents"><span class="stats-sq mod-agent small"><img src="/img/vlr/game/agents/{agent}.png" alt="{agent}" title="{agent.title()}"></span></div></div>'
        + cell("rating2", "1.05") + cell("acs", "241")
        + '<div class="ovw-cell mod-kda"><span class="stats-sq mod-kda">'
        + kda("kills", k) + '<span class="num-space">/</span>' + kda("deaths", d)
        + '<span class="num-space">/</span>' + kda("assists", a) + '</span></div>'
        + cell("kd-diff", k - d) + cell("kast", "73%") + cell("adr", "160") + cell("hsp", "24%")
        + cell("fb", "3") + cell("fd", "2") + cell("fk-diff", "+1") + '</div>'
    )


def _game(gid, mapname, s1, s2, played=True):
    head = ('<div class="ovw-row mod-head"><div class="ovw-th"></div>'
            '<div class="ovw-th ovw-sort js-ovw-sort" data-col="rating2">R</div></div>')
    rows = ""
    if played:
        rows = "".join(_row(f"tl{i}", 100 + i, "TL", "sova", 12 + i, 15, 5) for i in range(5))
        rows += "".join(_row(f"prx{i}", 200 + i, "PRX", "jett", 20 + i, 10, 3) for i in range(5))
    return (
        f'<div class="vm-stats-game" data-game-id="{gid}"><div class="vm-stats-game-header">'
        f'<div class="team"><div class="score">{s1}</div><div><div class="team-name"> Team Liquid </div></div></div>'
        f'<div class="map"><div><span style="position: relative;"> {mapname} '
        f'<span class="picked mod-2 ge-text-light"> PICK </span></span></div></div>'
        f'<div class="team mod-right"><div><div class="team-name"> Paper Rex </div></div>'
        f'<div class="score mod-win">{s2}</div></div></div>'
        f'<div></div><div class="ovw-filter"></div><div><div class="ovw-scroll-wrap"><div class="ovw-scroll js-drag-scroll">'
        f'<div class="ovw-table">{head}{rows}</div></div></div></div></div>'
    )


PAGE = (
    '<div class="match-header"><div class="match-header-event-series"> Group Stage: Opening (C) </div>'
    '<div class="moment-tz-convert" data-utc-ts="2026-09-24 05:00:00"> Thursday </div>'
    '<div class="match-header-link-name mod-1"><div class="wf-title-med"> Team Liquid </div></div>'
    '<div class="match-header-vs-note"> final </div><div class="match-header-vs-note"> Bo3 </div>'
    '<div class="match-header-link-name mod-2"><div class="wf-title-med"> Paper Rex </div></div></div>'
    '<div class="vm-stats">'
    + _game("283184", "Ascent", 4, 13)
    + '<div class="vm-stats-game" data-game-id="all"></div>'
    + _game("283185", "Haven", 13, 11)
    + _game("283186", "TBD", 0, 0, played=False)
    + '</div>'
)


def test_parse_div_layout():
    rows = parse_match(PAGE, 753455, 2766, "Valorant Champions 2026")
    assert len(rows) == 20                                   # 2 played maps x 10 players
    r = rows[0]
    assert (r.map, r.team, r.opp, r.team_rounds, r.opp_rounds) == ("Ascent", "Team Liquid", "Paper Rex", 4, 13)
    assert (r.player, r.player_id, r.agent) == ("tl0", 100, "sova")
    assert (r.rating, r.acs, r.k, r.d, r.a, r.kast, r.adr, r.hs, r.fk, r.fd) == (1.05, 241, 12, 15, 5, 73, 160, 24, 3, 2)
    prx = [x for x in rows if x.map == "Ascent" and x.team == "Paper Rex"]
    assert len(prx) == 5 and prx[0].team_rounds == 13 and prx[0].agent == "jett"
    assert {x.map_order for x in rows} == {1, 2} and rows[0].best_of == 3 and rows[0].completed
    assert rows[0].date == "2026-09-24"
