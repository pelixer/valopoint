// Append-only prediction ledger (web/public/data/ledger.json, written by `valopoint ledger`).
// The prediction that counts for a finished match is the last snapshot recorded
// before its start time — never recomputed afterwards.

const before = (e, time) => !time || Date.parse(e.recorded_at) < Date.parse(time);

export function lockedFor(ledger, bracketId, match) {
  let last = null;
  for (const e of ledger ?? []) if (e.bracket === bracketId && e.match === match.id && before(e, match.time)) last = e;
  return last;
}

// finished matches with a locked prediction: [{...entry, winner, correct}]
export function lockedResults(ledger, brackets) {
  const out = [];
  for (const br of brackets ?? []) {
    for (const m of br.matches) {
      const w = br.results?.[m.id];
      if (!w) continue;
      const e = lockedFor(ledger, br.id, m);
      if (e && (w === e.team_a || w === e.team_b)) out.push({ ...e, winner: w, correct: (e.p > 0.5) === (w === e.team_a) });
    }
  }
  return out.sort((a, b) => Date.parse(a.match_time ?? 0) - Date.parse(b.match_time ?? 0));
}

export function summarize(rows) {
  if (!rows.length) return null;
  let ll = 0, br = 0, exp = 0;
  for (const r of rows) {
    const y = r.winner === r.team_a ? 1 : 0;
    const p = Math.min(Math.max(r.p, 1e-6), 1 - 1e-6);
    ll -= y * Math.log(p) + (1 - y) * Math.log(1 - p);
    br += (p - y) ** 2;
    exp += Math.max(p, 1 - p);
  }
  const n = rows.length;
  return { n, correct: rows.filter((r) => r.correct).length, expected: exp, logLoss: ll / n, brier: br / n };
}
