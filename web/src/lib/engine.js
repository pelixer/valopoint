// Prediction engine — mirrors valopoint/model.py + predict.py so the browser can
// run "what if" scenarios and bracket Monte Carlo without a server.

export function winFromQ(q) {
  q = Math.min(0.98, Math.max(0.02, q));
  const r = 1 - q;
  let p = 0;
  let c = 1; // C(12+k, k)
  for (let k = 0; k < 12; k++) {
    if (k > 0) c = (c * (12 + k)) / k;
    p += c * q ** 13 * r ** k;
  }
  const tie = 2704156 * q ** 12 * r ** 12; // C(24,12)
  return p + (tie * q * q) / (q * q + r * r);
}

export const logit = (p) => {
  p = Math.min(1 - 1e-6, Math.max(1e-6, p));
  return Math.log(p / (1 - p));
};
export const sigmoid = (x) => 1 / (1 + Math.exp(-x));

export function createEngine(model) {
  const teams = Object.fromEntries(model.teams.map((t) => [t.name, t]));
  const beta = model.calib?.beta ?? 1;
  const gamma = (r) => model.regions?.[r]?.gamma ?? 0;
  const cache = new Map();

  function mapProb(a, b, map) {
    const A = teams[a], B = teams[b];
    if (!A || !B) return 0.5;
    const dS = (A.theta[map] ?? 0) - (B.theta[map] ?? 0);
    return sigmoid(beta * logit(winFromQ(0.5 + dS)) + gamma(A.region) - gamma(B.region));
  }

  function series(a, b, bestOf = 3) {
    const key = `${a}|${b}|${bestOf}`;
    if (cache.has(key)) return cache.get(key);
    const pmap = Object.fromEntries(model.maps.map((m) => [m, mapProb(a, b, m)]));
    const vA = vetoMaps(pmap, bestOf, true);
    const vB = vetoMaps(pmap, bestOf, false);
    let out;
    if (model.veto_model) {
      // map order from the teams' recent ban/pick tendencies (veto model)
      const seqs = vetoSequences(model.veto_model, a, b, model.maps, bestOf);
      let p = 0, tot = 0;
      const presence = {}, lines = {};
      for (const [seq, pr] of seqs) {
        const ps = seq.map((m) => pmap[m]);
        p += pr * seriesOrdered(ps);
        tot += pr;
        for (const m of seq) presence[m] = (presence[m] ?? 0) + pr;
        for (const [k, q] of Object.entries(scorelines(ps))) lines[k] = (lines[k] ?? 0) + pr * q;
      }
      for (const k in lines) lines[k] /= Math.max(tot, 1e-9);
      out = { p: p / Math.max(tot, 1e-9), pmap, basis: 'veto_model', seqs: seqs.slice(0, 5), presence, lines, veto: { aFirst: vA, bFirst: vB } };
    } else {
      const p = (seriesOrdered(vA.map((m) => pmap[m])) + seriesOrdered(vB.map((m) => pmap[m]))) / 2;
      out = { p, pmap, basis: 'greedy', seqs: [[vA, 0.5], [vB, 0.5]], presence: null, veto: { aFirst: vA, bFirst: vB } };
    }
    cache.set(key, out);
    return out;
  }

  return { teams, mapProb, series };
}

// uppercase = ban, lowercase = pick; A/a = team with first ban
const VETO = { 1: 'ABABAB', 3: 'ABabAB', 5: 'ABabab' };

export function vetoMaps(pmap, bestOf, aFirst = true) {
  const order = VETO[bestOf] ?? VETO[3];
  const left = Object.keys(pmap);
  const picks = [];
  for (const ch of order) {
    if (left.length <= 1) break;
    const aTurn = (ch.toUpperCase() === 'A') === aFirst;
    const score = (m) => (aTurn ? pmap[m] : 1 - pmap[m]);
    let best = left[0];
    for (const m of left) {
      if (ch === ch.toUpperCase() ? score(m) < score(best) : score(m) > score(best)) best = m;
    }
    left.splice(left.indexOf(best), 1);
    if (ch !== ch.toUpperCase()) picks.push(best);
  }
  return [...picks, ...left.slice(0, 1)];
}

/**
 * Veto model (mirrors valopoint/veto.py VetoModel.sequences): each ban / pick is drawn
 * in proportion to the team's recent ban/pick counts, shrunk toward the league-wide
 * tendency. Returns [[maps in play order], probability] sorted by probability,
 * averaged over who bans first.
 */
export function vetoSequences(vm, a, b, pool, bestOf = 3) {
  const order = VETO[bestOf] ?? VETO[3];
  const acc = new Map();
  const weights = (team, act, left) => {
    const own = (act === 'ban' ? vm.ban : vm.pick)?.[team] ?? {};
    const glob = (act === 'ban' ? vm.g_ban : vm.g_pick) ?? {};
    const gtot = left.reduce((s, m) => s + (glob[m] ?? 0), 0) || 1;
    return left.map((m) => (own[m] ?? 0) + (vm.prior * ((glob[m] ?? 0) + 0.5)) / (gtot + 0.5 * left.length));
  };
  function rec(i, left, picks, pr, first, second) {
    if (pr < 1e-6) return;
    if (i === order.length || left.length <= 1) {
      const seq = [...picks, ...left.slice(0, 1)];
      const k = seq.join('|');
      acc.set(k, (acc.get(k) ?? 0) + pr);
      return;
    }
    const ch = order[i];
    const team = ch.toUpperCase() === 'A' ? first : second;
    const act = ch === ch.toUpperCase() ? 'ban' : 'pick';
    const w = weights(team, act, left);
    const tot = w.reduce((s, x) => s + x, 0);
    left.forEach((m, j) => {
      const rest = left.filter((x) => x !== m);
      rec(i + 1, rest, act === 'pick' ? [...picks, m] : picks, (pr * w[j]) / tot, first, second);
    });
  }
  rec(0, [...pool], [], 0.5, a, b);
  rec(0, [...pool], [], 0.5, b, a);
  return [...acc.entries()].map(([k, p]) => [k.split('|'), p]).sort((x, y) => y[1] - x[1]);
}

export function seriesOrdered(ps) {
  const need = Math.floor(ps.length / 2) + 1;
  let dist = new Map([['0,0', 1]]);
  let win = 0;
  for (const p of ps) {
    const nd = new Map();
    for (const [k, pr] of dist) {
      const [a, b] = k.split(',').map(Number);
      if (a + 1 === need) win += pr * p;
      else nd.set(`${a + 1},${b}`, (nd.get(`${a + 1},${b}`) ?? 0) + pr * p);
      if (b + 1 < need) nd.set(`${a},${b + 1}`, (nd.get(`${a},${b + 1}`) ?? 0) + pr * (1 - p));
    }
    dist = nd;
  }
  return win;
}

// ---------------------------------------------------------------- bracket

function resolve(ref, seeds, res) {
  if (ref.startsWith('W:')) return res[ref.slice(2)]?.[0];
  if (ref.startsWith('L:')) return res[ref.slice(2)]?.[1];
  const m = /^S(\d+)$/.exec(ref);
  return m ? seeds[Number(m[1]) - 1] : ref;
}

// seeded PRNG so repeated runs are stable
function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Monte Carlo over a bracket DAG. `locked` = {matchId: winnerName} fixes results
 * that already happened (or "what if" choices).
 * Returns champion probs, per-match participant/winner probs.
 */
export function simulateBracket(engine, bracket, locked = {}, n = 20000, seed = 1) {
  const rnd = mulberry32(seed);
  const seeds = bracket.teams;
  const champ = {};
  const slot = {}; // matchId -> {team: count}  (appearances)
  const wins = {}; // matchId -> {team: count}
  for (const m of bracket.matches) { slot[m.id] = {}; wins[m.id] = {}; }
  const finalId = bracket.final ?? bracket.matches.at(-1).id;

  for (let i = 0; i < n; i++) {
    const res = {};
    for (const m of bracket.matches) {
      const a = resolve(m.a, seeds, res);
      const b = resolve(m.b, seeds, res);
      slot[m.id][a] = (slot[m.id][a] ?? 0) + 1;
      slot[m.id][b] = (slot[m.id][b] ?? 0) + 1;
      let w;
      const lk = locked[m.id];
      if (lk === a || lk === b) w = lk;
      else w = rnd() < engine.series(a, b, m.best_of ?? 3).p ? a : b;
      res[m.id] = [w, w === a ? b : a];
      wins[m.id][w] = (wins[m.id][w] ?? 0) + 1;
    }
    const c = res[finalId][0];
    champ[c] = (champ[c] ?? 0) + 1;
  }
  const norm = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v / n]).sort((x, y) => y[1] - x[1]));
  return {
    champion: norm(champ),
    slot: Object.fromEntries(Object.entries(slot).map(([k, v]) => [k, norm(v)])),
    wins: Object.fromEntries(Object.entries(wins).map(([k, v]) => [k, norm(v)])),
  };
}

/** Probability of each final score for team A, given ordered per-map win probs. */
export function scorelines(ps) {
  const need = Math.floor(ps.length / 2) + 1;
  let dist = new Map([['0,0', 1]]);
  const done = {};
  for (const p of ps) {
    const nd = new Map();
    for (const [k, pr] of dist) {
      const [a, b] = k.split(',').map(Number);
      for (const [a2, b2, q] of [[a + 1, b, p], [a, b + 1, 1 - p]]) {
        const key = `${a2}-${b2}`;
        if (a2 === need || b2 === need) done[key] = (done[key] ?? 0) + pr * q;
        else nd.set(`${a2},${b2}`, (nd.get(`${a2},${b2}`) ?? 0) + pr * q);
      }
    }
    dist = nd;
  }
  return done;
}
