<script>
  import { app } from '../lib/store.svelte.js';
  import { ROLE_LABEL, cap, fx } from '../lib/format.js';
  import Radar from '../lib/Radar.svelte';

  let { name } = $props();
  let t = $derived(app.engine.teams[name]);
  let roster = $derived(t ? t.roster.map((id) => ({ id, ...app.model.players[id] })).filter((p) => p.name) : []);
  let maps = $derived(t ? [...app.model.maps].sort((a, b) => t.theta[b] - t.theta[a]) : []);
  let axes = $derived(app.model.style_axes ?? []);
  let teamStyle = $derived.by(() => {
    const ps = roster.filter((p) => p.style);
    if (!ps.length) return null;
    return Object.fromEntries(axes.map((a) => [a.key, ps.reduce((s, p) => s + p.style[a.key], 0) / ps.length]));
  });
</script>

<a class="back" href="#/teams">‹ 팀</a>
{#if !t}
  <p>팀을 찾을 수 없습니다.</p>
{:else}
  <h1>{t.name} <span class="badge {t.region}">{t.region}</span></h1>
  <div class="card"><span class="muted">팀 PP</span> <span class="pp" style="font-size:22px">{fx(t.pp, 0)}</span></div>

  <h2>로스터</h2>
  <div class="list">
    {#each roster as p}
      <a class="row" href={`#/player/${p.id}`}>
        <div class="grow">
          <div class="title">{p.name}</div>
          <span class="muted small">{ROLE_LABEL[p.role] ?? p.role} · {p.rounds} 라운드</span>
        </div>
        <span class="pp">{fx(p.pp)}</span>
      </a>
    {/each}
  </div>

  {#if teamStyle}
    <h2>팀 속성 (로스터 평균)</h2>
    <div class="card">
      <Radar {axes} series={[{ values: teamStyle, color: 'var(--accent)', label: t.name }, { values: Object.fromEntries(axes.map((a) => [a.key, 50])), color: 'var(--muted)', label: '평균', dashed: true }]} />
    </div>
  {/if}

  <h2>맵별 팀 PP</h2>
  <div class="card">
    <table>
      <tbody>
        {#each maps as m}
          <tr><td>{cap(m)}</td><td class="num">{fx(500 + 1000 * t.theta[m], 1)}</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
