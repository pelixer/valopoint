<script>
  import { app, persisted } from '../lib/store.svelte.js';
  import { simulateBracket } from '../lib/engine.js';
  import { pct } from '../lib/format.js';

  const brackets = app.model.brackets ?? [];
  const store = persisted('bracket-locks', {});
  let idx = $state(0);
  let br = $derived(brackets[idx]);
  // official results from the data file + my own locks / what-ifs
  let mine = $state(store.get());
  let locked = $derived(br ? { ...(br.results ?? {}), ...(mine[br.id] ?? {}) } : {});
  let sim = $derived(br ? simulateBracket(app.engine, br, locked, 20000) : null);

  function known(ref, res) {
    if (ref.startsWith('W:')) return res[ref.slice(2)]?.[0];
    if (ref.startsWith('L:')) return res[ref.slice(2)]?.[1];
    const m = /^S(\d+)$/.exec(ref);
    return m ? br.teams[Number(m[1]) - 1] : ref;
  }
  // teams determined by seeds + locked results (null if still open)
  let fixed = $derived.by(() => {
    if (!br) return {};
    const res = {}, out = {};
    for (const m of br.matches) {
      const a = known(m.a, res), b = known(m.b, res);
      out[m.id] = { a, b };
      const w = locked[m.id];
      if (a && b && (w === a || w === b)) res[m.id] = [w, w === a ? b : a];
    }
    return out;
  });

  function lock(mid, team) {
    const cur = { ...(mine[br.id] ?? {}) };
    if (cur[mid] === team) delete cur[mid];
    else cur[mid] = team;
    mine = { ...mine, [br.id]: cur };
    store.set(mine);
  }
  function reset() {
    mine = { ...mine, [br.id]: {} };
    store.set(mine);
  }
  const top = (o, n) => Object.entries(o ?? {}).slice(0, n);
</script>

<h1>대진표 시뮬레이션</h1>
{#if !brackets.length}
  <p class="muted">등록된 대진표가 없습니다. <code>data/brackets/*.json</code>에 추가하세요.</p>
{:else}
  {#if brackets.length > 1}
    <select bind:value={idx} style="margin-bottom:10px">
      {#each brackets as b, i}<option value={i}>{b.name}</option>{/each}
    </select>
  {/if}
  <p class="muted small">{br.name} · 20,000회 몬테카를로. 경기를 탭해 승자를 고정하면(실제 결과·가정) 나머지 확률이 즉시 갱신됩니다.</p>

  <h2>우승 확률</h2>
  <div class="list">
    {#each top(sim.champion, 16) as [t, p]}
      <div class="row">
        <div class="grow title">{t}</div>
        <div style="width:40%"><div class="bar"><span style="width:{p * 100}%"></span></div></div>
        <span class="num" style="width:48px; text-align:right">{pct(p, 1)}</span>
      </div>
    {/each}
  </div>

  <h2>경기 <button class="btn small" style="float:right" onclick={reset}>내 고정 초기화</button></h2>
  {#each br.matches as m}
    {@const fx_ = fixed[m.id]}
    <div class="card">
      <div class="muted small">{m.round ?? m.id} · Bo{m.best_of ?? 3}{br.results?.[m.id] ? ' · 공식 결과' : ''}</div>
      {#if fx_.a && fx_.b}
        {@const p = app.engine.series(fx_.a, fx_.b, m.best_of ?? 3).p}
        <div style="display:flex; gap:8px; margin-top:6px">
          {#each [[fx_.a, p], [fx_.b, 1 - p]] as [t, q]}
            <button class="btn" style="flex:1; text-align:left; {locked[m.id] === t ? 'border-color:var(--accent); background:#3a1f25' : ''}"
              onclick={() => lock(m.id, t)} disabled={!!br.results?.[m.id]}>
              <div style="font-weight:600">{t}</div>
              <div class="muted small">{locked[m.id] ? (locked[m.id] === t ? '승 (고정)' : '패') : pct(q)}</div>
            </button>
          {/each}
        </div>
      {:else}
        <div class="small" style="margin-top:6px">
          <span class="muted">진출 예상:</span>
          {#each top(sim.slot[m.id], 4) as [t, q], i}{i ? ', ' : ' '}{t} {pct(q)}{/each}
        </div>
      {/if}
    </div>
  {/each}
{/if}
