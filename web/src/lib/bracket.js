// Shared bracket helpers: which group/stage a match belongs to, and which teams
// are in each slot given official results + what-if locks.

const STAGES = {
  U: { label: '플레이오프 · 상위', color: 'var(--g-up)' },
  L: { label: '플레이오프 · 하위', color: 'var(--g-low)' },
  F: { label: '결승', color: 'var(--accent)' },
  X: { label: '기타', color: 'var(--muted)' },
};
const GROUP_COLORS = ['var(--g-a)', 'var(--g-b)', 'var(--g-c)', 'var(--g-d)', 'var(--g-e)', 'var(--g-f)'];

export function groupOf(m) {
  const g = /^([A-H])-/.exec(m.id);
  if (g) {
    const i = g[1].charCodeAt(0) - 65;
    return { key: g[1], label: `${g[1]}조`, color: GROUP_COLORS[i % GROUP_COLORS.length] };
  }
  if (m.id === 'GF') return { key: 'F', ...STAGES.F };
  if (/^U/.test(m.id)) return { key: 'U', ...STAGES.U };
  if (/^L/.test(m.id)) return { key: 'L', ...STAGES.L };
  return { key: 'X', ...STAGES.X };
}

function known(br, ref, res) {
  if (ref.startsWith('W:')) return res[ref.slice(2)]?.[0];
  if (ref.startsWith('L:')) return res[ref.slice(2)]?.[1];
  const m = /^S(\d+)$/.exec(ref);
  return m ? br.teams[Number(m[1]) - 1] : ref;
}

/** {matchId: {a, b}} — team names where determined, else undefined. */
export function resolveTeams(br, locked) {
  const res = {}, out = {};
  for (const m of br?.matches ?? []) {
    const a = known(br, m.a, res), b = known(br, m.b, res);
    out[m.id] = { a, b };
    const w = locked[m.id];
    if (a && b && (w === a || w === b)) res[m.id] = [w, w === a ? b : a];
  }
  return out;
}

/** GSL group table: wins/losses inside the group from official results. */
export function groupTable(br, key) {
  const t = {};
  for (const m of br.matches) {
    if (groupOf(m).key !== key) continue;
    for (const s of ['a', 'b']) if (!/^[WL]:/.test(m[s])) t[m[s]] ??= { w: 0, l: 0 };
    const w = br.results?.[m.id];
    if (!w) continue;
    const loser = w === m.a ? m.b : m.a;
    (t[w] ??= { w: 0, l: 0 }).w++;
    (t[loser] ??= { w: 0, l: 0 }).l++;
  }
  return Object.entries(t).sort((x, y) => y[1].w - x[1].w || x[1].l - y[1].l);
}
