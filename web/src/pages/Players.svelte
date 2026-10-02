<script>
  import { app } from '../lib/store.svelte.js';
  import { REGION_LABEL, ROLE_LABEL, cap, fx } from '../lib/format.js';
  import { badges, buildContext, highlights } from '../lib/profile.js';

  let region = $state('ALL');
  let role = $state('ALL');
  let map = $state('');
  let agent = $state('');
  let q = $state('');
  let open = $state({});
  const norm = (x) => (x ?? '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');

  const all = Object.entries(app.model.players).map(([id, p]) => ({ id, ...p }));
  const agents = [...new Set(all.flatMap((p) => Object.keys(p.agents)))].sort();
  let ctx = $derived(buildContext(app.model, app.brackets));
  let sections = $derived(highlights(ctx, 10));
  let tags = $derived(Object.fromEntries(all.map((p) => [p.id, badges(p, ctx)])));

  function value(p) {
    if (map && agent) return p.grid[map]?.[agent] != null ? { pp: p.grid[map][agent], n: null } : null;
    if (agent) return p.agents[agent] ? { pp: p.agents[agent].pp, n: p.agents[agent].rounds } : null;
    if (map) return p.maps[map] ? { pp: p.maps[map].pp, n: p.maps[map].rounds } : { pp: p.pp, n: 0 };
    return { pp: p.pp, n: p.rounds };
  }

  let searching = $derived(q.trim().length > 0);
  let rows = $derived(
    all
      .filter((p) => searching || ((region === 'ALL' || p.region === region) && (role === 'ALL' || p.role === role)))
      .filter((p) => !searching || norm(p.name).includes(norm(q.trim())) || norm(p.team).includes(norm(q.trim())))
      .map((p) => ({ p, v: searching ? { pp: p.pp, n: p.rounds } : value(p) }))
      .filter((r) => r.v)
      .sort((a, b) => b.v.pp - a.v.pp),
  );

  function jump(key) {
    document.getElementById(`hl-${key}`)?.scrollIntoView({ behavior: 'smooth', inline: 'start', block: 'nearest' });
  }
</script>

{#snippet tagRow(list, max)}
  {#if list.length}
    <div class="tags">
      {#each list.slice(0, max) as t}<span class="tag {t.tone}">{t.icon} {t.label}</span>{/each}
    </div>
  {/if}
{/snippet}

{#snippet playerRow(p, rank, right, sub, max)}
  <a class="row" href={`#/player/${p.id}`}>
    <span class="rank">{rank}</span>
    <div class="grow" style="min-width:0">
      <div class="title">{p.name}</div>
      <span class="muted small"><span class="badge {p.region}">{p.region}</span> {p.team} · {ROLE_LABEL[p.role] ?? p.role}{sub ? ` · ${sub}` : ''}</span>
      {@render tagRow(tags[p.id] ?? [], max)}
    </div>
    <span class="pp">{right}</span>
  </a>
{/snippet}

<h1>선수</h1>
<input class="search" type="search" placeholder="선수 또는 팀 검색" bind:value={q} id="player-search" autocomplete="off" />

{#if searching}
  <p class="muted small">{rows.length}명</p>
  <div class="list">
    {#each rows as { p, v }, i}
      {@render playerRow(p, i + 1, fx(v.pp), `${v.n}R`, 4)}
    {/each}
  </div>
{:else}
  <div class="chips" style="margin-top:4px">
    {#each sections as s}
      <button class="chip" onclick={() => jump(s.key)}>{s.icon} {s.title}</button>
    {/each}
  </div>
  <div class="hl-scroll">
    {#each sections as s}
      <section class="hl-card card" id={`hl-${s.key}`}>
        <div class="hl-head"><span class="hl-icon">{s.icon}</span> <b>{s.title}</b></div>
        {#each s.rows.slice(0, open[s.key] ? 10 : 5) as r, i}
          <a class="hl-row" href={`#/player/${r.p.id}`}>
            <span class="hl-rank" class:first={i === 0}>{i + 1}</span>
            <div style="flex:1; min-width:0">
              <div class="hl-name">{r.p.name} <span class="badge {r.p.region}">{r.p.region}</span></div>
              <div class="muted small hl-sub">{r.p.team} · {r.sub}</div>
            </div>
            <span class="hl-val">{r.value}</span>
          </a>
        {/each}
        {#if s.rows.length > 5}
          <button class="hl-more" onclick={() => (open = { ...open, [s.key]: !open[s.key] })}>{open[s.key] ? '접기' : `더 보기 (${s.rows.length})`}</button>
        {/if}
        <p class="muted small hl-note">{s.note}</p>
      </section>
    {/each}
  </div>

  <h2>전체 랭킹</h2>
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
      {@render playerRow(p, i + 1, fx(v.pp), v.n != null ? `${v.n}R` : '', 3)}
    {/each}
  </div>
{/if}

<style>
  .hl-scroll {
    display: flex; gap: 10px; overflow-x: auto; scroll-snap-type: x mandatory;
    margin: 0 -16px 8px; padding: 0 16px 6px; scroll-padding: 0 16px; scrollbar-width: none;
  }
  .hl-scroll::-webkit-scrollbar { display: none; }
  .hl-card { flex: 0 0 86%; max-width: 380px; scroll-snap-align: start; margin: 0; display: flex; flex-direction: column; }
  .hl-head { font-size: 16px; margin-bottom: 8px; }
  .hl-icon { font-size: 18px; }
  .hl-row { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-top: 1px solid var(--border); color: inherit; text-decoration: none; }
  .hl-rank { width: 22px; height: 22px; border-radius: 11px; background: var(--surface-2); color: var(--muted); font-size: 12px; display: grid; place-items: center; flex: none; }
  .hl-rank.first { background: var(--accent); color: #fff; }
  .hl-name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .hl-sub { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .hl-val { font-variant-numeric: tabular-nums; font-weight: 700; font-size: 16px; }
  .hl-more { background: none; border: 0; color: var(--accent); padding: 8px 0 0; font-size: 13px; text-align: left; cursor: pointer; }
  .hl-note { margin: auto 0 0; padding-top: 8px; }
</style>
