<script>
  import { app, persisted } from '../lib/store.svelte.js';
  import { cap, fx, pct } from '../lib/format.js';

  const saved = persisted('match', {});
  const names = app.model.teams.map((t) => t.name).sort();
  let a = $state(saved.get().a ?? app.model.teams[0]?.name);
  let b = $state(saved.get().b ?? app.model.teams[1]?.name);
  let bo = $state(saved.get().bo ?? 3);
  $effect(() => saved.set({ a, b, bo }));

  let f = $derived(a && b && a !== b ? app.engine.series(a, b, bo) : null);
  let maps = $derived(f ? Object.entries(f.pmap).sort((x, y) => y[1] - x[1]) : []);
  const tpp = (n) => app.engine.teams[n]?.pp;
</script>

<h1>매치 예측</h1>
<div style="display:flex; gap:8px; align-items:center; margin-bottom:10px">
  <select bind:value={a}>{#each names as n}<option>{n}</option>{/each}</select>
  <button class="btn" onclick={() => ([a, b] = [b, a])} aria-label="swap">⇄</button>
  <select bind:value={b}>{#each names as n}<option>{n}</option>{/each}</select>
</div>
<div class="chips">
  {#each [1, 3, 5] as n}<button class="chip" class:on={bo === n} onclick={() => (bo = n)}>Bo{n}</button>{/each}
</div>

{#if f}
  <div class="card">
    <div class="split">
      <div class="a" style="width:{Math.max(f.p * 100, 18)}%">{a} {pct(f.p)}</div>
      <div class="b" style="width:{Math.max((1 - f.p) * 100, 18)}%">{pct(1 - f.p)} {b}</div>
    </div>
    <p class="muted small">팀 PP {fx(tpp(a), 0)} vs {fx(tpp(b), 0)}</p>
  </div>

  <h2>맵별 승률 ({a} 기준)</h2>
  <div class="list">
    {#each maps as [m, p]}
      <div class="row">
        <div style="width:78px">{cap(m)}</div>
        <div class="grow"><div class="bar"><span style="width:{p * 100}%"></span></div></div>
        <span class="num" style="width:44px; text-align:right">{pct(p)}</span>
      </div>
    {/each}
  </div>

  <h2>예상 맵 순서</h2>
  <div class="card small">
    <div><span class="muted">{a} 선밴:</span> {f.veto.aFirst.map(cap).join(' → ')}</div>
    <div><span class="muted">{b} 선밴:</span> {f.veto.bFirst.map(cap).join(' → ')}</div>
    <p class="muted">각 팀이 자기 승률이 가장 낮은 맵을 밴하고 가장 높은 맵을 픽한다고 가정. 두 순서의 평균이 시리즈 승률입니다.</p>
  </div>
{:else}
  <p class="muted">서로 다른 두 팀을 고르세요.</p>
{/if}
