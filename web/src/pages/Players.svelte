<script>
  import { app } from '../lib/store.svelte.js';
  import { REGION_LABEL, ROLE_LABEL, cap, fx } from '../lib/format.js';

  let region = $state('ALL');
  let role = $state('ALL');
  let map = $state('');
  let agent = $state('');

  const all = Object.entries(app.model.players).map(([id, p]) => ({ id, ...p }));
  const agents = [...new Set(all.flatMap((p) => Object.keys(p.agents)))].sort();

  function value(p) {
    if (map && agent) return p.grid[map]?.[agent] != null ? { pp: p.grid[map][agent], n: null } : null;
    if (agent) return p.agents[agent] ? { pp: p.agents[agent].pp, n: p.agents[agent].rounds } : null;
    if (map) return p.maps[map] ? { pp: p.maps[map].pp, n: p.maps[map].rounds } : { pp: p.pp, n: 0 };
    return { pp: p.pp, n: p.rounds };
  }

  let rows = $derived(
    all
      .filter((p) => (region === 'ALL' || p.region === region) && (role === 'ALL' || p.role === role))
      .map((p) => ({ p, v: value(p) }))
      .filter((r) => r.v)
      .sort((a, b) => b.v.pp - a.v.pp),
  );
</script>

<h1>선수 파워포인트</h1>
<div class="chips">
  {#each ['ALL', 'AMER', 'EMEA', 'PAC', 'CN'] as r}
    <button class="chip" class:on={region === r} onclick={() => (region = r)}>{r === 'ALL' ? '전체' : REGION_LABEL[r]}</button>
  {/each}
</div>
<div class="chips">
  {#each ['ALL', 'duelist', 'initiator', 'controller', 'sentinel'] as r}
    <button class="chip" class:on={role === r} onclick={() => (role = r)}>{r === 'ALL' ? '전체 역할' : ROLE_LABEL[r]}</button>
  {/each}
</div>
<div style="display:flex; gap:8px; margin-bottom:10px">
  <select bind:value={map}>
    <option value="">모든 맵</option>
    {#each app.model.maps as m}<option value={m}>{cap(m)}</option>{/each}
  </select>
  <select bind:value={agent}>
    <option value="">모든 요원</option>
    {#each agents as a}<option value={a}>{cap(a)}</option>{/each}
  </select>
</div>
<p class="muted small">PP 100 = 평균 선수. +10 PP ≈ 팀 라운드 승률 +1%p 기여. 표본이 적은 조합은 선수 전체값 쪽으로 축소 추정됩니다.</p>
<div class="list">
  {#each rows as { p, v }, i}
    <a class="row" href={`#/player/${p.id}`}>
      <span class="rank">{i + 1}</span>
      <div class="grow">
        <div class="title">{p.name}</div>
        <span class="muted small"><span class="badge {p.region}">{p.region}</span> {p.team} · {ROLE_LABEL[p.role] ?? p.role}{v.n != null ? ` · ${v.n}R` : ''}</span>
      </div>
      <span class="pp">{fx(v.pp)}</span>
    </a>
  {/each}
</div>
