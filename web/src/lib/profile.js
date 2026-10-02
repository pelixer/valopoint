// Player highlights and personality tags, from model.players[*].profile
// (built by valopoint/highlights.py; descriptive only, not used for prediction).
import { cap } from './format.js';

const sgn = (x, d = 1) => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(d)}`;

export function buildContext(model, brackets) {
  const players = Object.entries(model.players).map(([id, p]) => ({ id, ...p, prof: p.profile ?? {} }));
  // teams of the international event whose bracket is loaded (e.g. Champions)
  const br = (brackets ?? []).find((b) => /champions|masters/i.test(b.name ?? '')) ?? null;
  const participants = new Set(br?.teams ?? []);
  const eventName = (br?.name ?? model.meta.current_event?.name ?? '국제전').replace(/^Valorant /, '');

  // agent masters: best agent PP with a real sample (>= 300 rounds ≈ 14 maps)
  const masters = {};
  for (const p of players) {
    for (const [a, v] of Object.entries(p.agents ?? {})) {
      if (v.rounds < 300) continue;
      if (!masters[a] || v.pp > masters[a].pp) masters[a] = { id: p.id, pp: v.pp, rounds: v.rounds };
    }
  }
  const agentPop = {};
  for (const p of players) for (const [a, v] of Object.entries(p.agents ?? {})) agentPop[a] = (agentPop[a] ?? 0) + v.rounds;

  // best map relative to the player's own level (>= 260 rounds on the map)
  const bestMap = (p) => {
    let best = null;
    for (const [m, v] of Object.entries(p.maps ?? {})) {
      if (v.rounds < 260) continue;
      const d = v.pp - p.pp;
      if (!best || d > best.d) best = { map: m, d, rounds: v.rounds };
    }
    return best;
  };
  const signature = (p) => {
    const tot = Object.values(p.agents ?? {}).reduce((s, v) => s + v.rounds, 0);
    const [a, v] = Object.entries(p.agents ?? {}).sort((x, y) => y[1].rounds - x[1].rounds)[0] ?? [];
    return a ? { agent: a, share: v.rounds / Math.max(tot, 1) } : null;
  };
  const rankOf = (list, id) => list.findIndex((p) => p.id === id) + 1;
  const byPP = [...players].sort((a, b) => b.pp - a.pp);

  return { players, participants, eventName, masters, agentPop, bestMap, signature, byPP, rankOf, styleAxes: model.style_axes ?? [] };
}

const top = (arr, f, n) => arr.filter((p) => f(p) != null).sort((a, b) => f(b) - f(a)).slice(0, n);

/** Highlight sections for the Players page: [{key, icon, title, note, rows:[{p, value, sub}]}] */
export function highlights(ctx, n = 10) {
  const P = ctx.players;
  const inEvent = (p) => ctx.participants.has(p.team);
  const out = [];
  const winLoss = (w, maps) => `${w}승 ${maps - w}패`;

  const cur = top(P, (p) => (p.prof.current?.maps >= 3 ? p.prof.current.pp : null), n);
  if (cur.length) out.push({
    key: 'mvp', icon: '⭐', title: `${ctx.eventName} MVP 레이스`,
    note: '이번 대회 맵 퍼포먼스(상대 보정, 표본이 적으면 평소 PP 쪽으로 축소).',
    rows: cur.map((p) => ({ p, value: p.prof.current.pp.toFixed(1), sub: `${p.prof.current.maps}맵 ${winLoss(p.prof.current.map_wins, p.prof.current.maps)}` })),
  });

  out.push({
    key: 'rising', icon: '🔥', title: '요즘 뜨는 선수',
    note: '최근 60일 퍼포먼스 − 그 전 10개월(둘 다 표본 크기만큼 축소). 최근 8맵 이상.',
    rows: top(P, (p) => (p.prof.form?.maps >= 8 ? p.prof.form.delta : null), n)
      .map((p) => ({ p, value: sgn(p.prof.form.delta), sub: `최근 ${p.prof.form.recent.toFixed(0)} ← 이전 ${p.prof.form.before.toFixed(0)} · ${p.prof.form.maps}맵` })),
  });

  out.push({
    key: 'steady', icon: '🧊', title: '가장 꾸준한 선수',
    note: '평균 이상(PP 100+) 선수 중 최근 1년 맵별 기복이 같은 역할 평균보다 가장 작은 선수. 하위 25% 경기 성적도 함께.',
    rows: top(P, (p) => (p.pp >= 100 && p.prof.steady?.rel ? -p.prof.steady.rel : null), n)
      .map((p) => ({ p, value: `−${((1 - p.prof.steady.rel) * 100).toFixed(0)}%`, sub: `기복 ${p.prof.steady.sd.toFixed(0)} · 하위 25% 경기 ${p.prof.steady.floor.toFixed(0)} · ${p.prof.steady.maps}맵` })),
  });

  out.push({
    key: 'career', icon: '🏆', title: '국제전 커리어',
    note: '최근 2년 국제전(마스터즈·챔피언스) 퍼포먼스. 국제전 2회·15맵 이상, 표본이 적으면 리그 성적 쪽으로 축소.',
    rows: top(P, (p) => (p.prof.intl?.events >= 2 && p.prof.intl.maps >= 15 ? p.prof.intl.pp : null), n)
      .map((p) => ({ p, value: p.prof.intl.pp.toFixed(1), sub: `국제전 ${p.prof.intl.events}회 · ${winLoss(p.prof.intl.map_wins, p.prof.intl.maps)}` })),
  });

  if (ctx.participants.size) {
    out.push({
      key: 'league', icon: '🌏', title: `${ctx.eventName} 참가 · 지역리그 최고 성적`,
      note: '이번 국제전 참가 선수의 직전 지역리그 퍼포먼스.',
      rows: top(P.filter(inEvent), (p) => p.prof.league?.pp, n)
        .map((p) => ({ p, value: p.prof.league.pp.toFixed(1), sub: `${p.prof.league.event} · ${p.prof.league.maps}맵 ${winLoss(p.prof.league.map_wins, p.prof.league.maps)}` })),
    });
    out.push({
      key: 'power', icon: '⚡', title: `${ctx.eventName} 참가 · 파워 Top`,
      note: '이번 국제전 참가 선수의 PP(예측에 쓰는 값).',
      rows: top(P.filter(inEvent), (p) => p.pp, n).map((p) => ({ p, value: p.pp.toFixed(1), sub: `${p.rounds}라운드` })),
    });
  }

  out.push({
    key: 'bigstage', icon: '🏟️', title: '큰 무대 체질',
    note: '국제전 퍼포먼스 − 지역리그 퍼포먼스. 국제전 15맵 이상.',
    rows: top(P, (p) => (p.prof.intl?.maps >= 15 ? p.prof.intl.big_stage : null), n)
      .map((p) => ({ p, value: sgn(p.prof.intl.big_stage), sub: `국제전 ${p.prof.intl.pp.toFixed(0)} · 리그 ${p.prof.intl.league_pp.toFixed(0)}` })),
  });

  const agents = Object.entries(ctx.masters).sort((a, b) => (ctx.agentPop[b[0]] ?? 0) - (ctx.agentPop[a[0]] ?? 0)).slice(0, n);
  out.push({
    key: 'agent', icon: '👑', title: '요원 장인',
    note: '요원별 PP 1위(그 요원 300라운드 이상). 많이 쓰이는 요원 순.',
    rows: agents.map(([a, v]) => {
      const p = ctx.players.find((x) => x.id === v.id);
      return { p, value: v.pp.toFixed(1), sub: `${cap(a)} · ${v.rounds}R`, tag: cap(a) };
    }),
  });

  out.push({
    key: 'map', icon: '🗺️', title: '맵 스페셜리스트',
    note: '자기 평균 대비 특정 맵에서 가장 강한 선수(그 맵 260라운드 이상).',
    rows: top(P, (p) => ctx.bestMap(p)?.d ?? null, n)
      .map((p) => { const b = ctx.bestMap(p); return { p, value: sgn(b.d), sub: `${cap(b.map)} ${(p.pp + b.d).toFixed(0)} (평균 ${p.pp.toFixed(0)})` }; }),
  });
  return out.filter((s) => s.rows.length);
}

/** Personality tags for one player: [{icon, label, tone}] (tone: good | bad | neutral) */
export function badges(p, ctx) {
  const prof = p.profile ?? p.prof ?? {};
  const out = [];
  if (prof.form?.maps >= 8 && prof.form.delta >= 5) out.push({ icon: '🔥', label: `상승세 ${sgn(prof.form.delta)}`, tone: 'good' });
  if (prof.form?.maps >= 8 && prof.form.delta <= -5) out.push({ icon: '📉', label: `하락세 ${sgn(prof.form.delta)}`, tone: 'bad' });
  const id = p.id;
  const crowns = Object.entries(ctx.masters).filter(([, v]) => v.id === id)
    .sort((x, y) => (ctx.agentPop[y[0]] ?? 0) - (ctx.agentPop[x[0]] ?? 0)).map(([a]) => cap(a));
  if (crowns.length) out.push({ icon: '👑', label: `${crowns.join('·')} 1위`, tone: 'good' });
  if (prof.steady?.rel && prof.steady.rel <= 0.85) out.push({ icon: '🧊', label: '꾸준함', tone: 'good' });
  if (prof.steady?.rel && prof.steady.rel >= 1.2) out.push({ icon: '🎢', label: '기복 큼', tone: 'neutral' });
  if (prof.intl?.maps >= 15 && prof.intl.big_stage >= 5) out.push({ icon: '🏟️', label: '큰 무대 체질', tone: 'good' });
  if (prof.intl?.events >= 3) out.push({ icon: '🌍', label: `국제전 ${prof.intl.events}회`, tone: 'neutral' });
  if (!prof.intl) out.push({ icon: '🆕', label: '2년 내 국제전 없음', tone: 'neutral' });
  const sig = ctx.signature(p);
  if (sig && sig.share >= 0.75) out.push({ icon: '🎯', label: `${cap(sig.agent)} 원픽 ${(sig.share * 100).toFixed(0)}%`, tone: 'neutral' });
  const bm = ctx.bestMap(p);
  if (bm && bm.d >= 3) out.push({ icon: '🗺️', label: `${cap(bm.map)} 강자`, tone: 'good' });
  if (p.style) {
    const best = ctx.styleAxes.map((a) => ({ ...a, v: p.style[a.key] })).sort((x, y) => y.v - x.v)[0];
    if (best && best.v >= 85) out.push({ icon: '✨', label: `${best.label} 상위 ${Math.max(1, 100 - Math.round(best.v))}%`, tone: 'neutral' });
  }
  return out;
}
