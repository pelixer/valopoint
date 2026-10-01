import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { winFromQ, seriesOrdered, vetoMaps, createEngine, simulateBracket } from './engine.js';

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test('map / series math matches python', () => {
  close(winFromQ(0.5), 0.5);
  assert.ok(winFromQ(0.55) > 0.6);
  close(seriesOrdered([0.6, 0.6, 0.6]), 0.648);
  close(seriesOrdered([0.5, 0.5, 0.5, 0.5, 0.5]), 0.5);
});

test('veto order matches python', () => {
  const pm = { a: 0.9, b: 0.8, c: 0.7, d: 0.5, e: 0.3, f: 0.2, g: 0.1 };
  assert.deepEqual(vetoMaps(pm, 3, true), ['b', 'f', 'd']);
  assert.equal(vetoMaps(pm, 1).length, 1);
  assert.equal(vetoMaps(pm, 5).length, 5);
});

test('bracket probabilities sum to 1 and locks are respected', () => {
  const model = JSON.parse(readFileSync(new URL('../../public/data/model.json', import.meta.url)));
  const eng = createEngine(model);
  // build an 8-team double-elim bracket from the model's own top teams
  // (model.brackets may be empty with real data until a bracket is registered)
  const t = model.teams.slice(0, 8).map((x) => x.name);
  const br = model.brackets?.[0] ?? {
    teams: t, final: 'GF',
    matches: [
      { id: 'Q1', a: 'S1', b: 'S8' }, { id: 'Q2', a: 'S4', b: 'S5' }, { id: 'Q3', a: 'S2', b: 'S7' }, { id: 'Q4', a: 'S3', b: 'S6' },
      { id: 'S1', a: 'W:Q1', b: 'W:Q2' }, { id: 'S2', a: 'W:Q3', b: 'W:Q4' },
      { id: 'L1', a: 'L:Q1', b: 'L:Q2' }, { id: 'L2', a: 'L:Q3', b: 'L:Q4' },
      { id: 'L3', a: 'W:L1', b: 'L:S2' }, { id: 'L4', a: 'W:L2', b: 'L:S1' },
      { id: 'UF', a: 'W:S1', b: 'W:S2' }, { id: 'LS', a: 'W:L3', b: 'W:L4' },
      { id: 'LF', a: 'L:UF', b: 'W:LS', best_of: 5 }, { id: 'GF', a: 'W:UF', b: 'W:LF', best_of: 5 },
    ],
  };
  const out = simulateBracket(eng, br, {}, 3000);
  close(Object.values(out.champion).reduce((a, b) => a + b, 0), 1, 1e-9);
  const lockTeam = br.teams[7]; // lowest seed wins its first match
  const out2 = simulateBracket(eng, br, { [br.matches[0].id]: lockTeam }, 3000);
  close(out2.wins[br.matches[0].id][lockTeam], 1);
});
