<script>
  import { app } from '../lib/store.svelte.js';
  import { ROLE_LABEL, cap, fx, heat } from '../lib/format.js';
  import Radar from '../lib/Radar.svelte';

  let { id } = $props();
  let p = $derived(app.model.players[id]);
  let agents = $derived(p ? Object.entries(p.agents).sort((a, b) => b[1].rounds - a[1].rounds) : []);
  let maps = $derived(p ? Object.keys(p.grid) : []);
  let axes = $derived(app.model.style_axes ?? []);
  // the two most distinctive axes (furthest from the median), for a one-line summary
  let traits = $derived(p?.style ? axes.map((a) => ({ ...a, v: p.style[a.key] }))
    .sort((x, y) => Math.abs(y.v - 50) - Math.abs(x.v - 50)).slice(0, 2) : []);
</script>

<a class="back" href="#/players">‹ 선수</a>
{#if !p}
  <p>선수를 찾을 수 없습니다.</p>
{:else}
  <h1>{p.name}</h1>
  <div class="card">
    <a href={`#/team/${encodeURIComponent(p.team)}`} style="color:inherit">{p.team}</a>
    <span class="badge {p.region}">{p.region}</span>
    <span class="muted">· {ROLE_LABEL[p.role] ?? p.role} · {p.rounds} 라운드</span>
    <div style="margin-top:6px"><span class="muted">PP</span> <span class="pp" style="font-size:24px">{fx(p.pp)}</span></div>
  </div>

  <h2>속성</h2>
  <div class="card">
    {#if p.style}
      <Radar {axes} series={[{ values: p.style, color: 'var(--accent)', label: p.name }, { values: Object.fromEntries(axes.map((a) => [a.key, 50])), color: 'var(--muted)', label: '같은 역할 평균', dashed: true }]} />
      <p class="small" style="margin-bottom:4px">
        {#each traits as t, i}{i ? ' · ' : ''}{t.label} {t.v >= 50 ? '높음' : '낮음'}{/each}
      </p>
      <p class="muted small" style="margin:0">같은 역할군 선수 대비 백분위(최근 1년, {p.style.maps}맵). 50 = 역할 평균. 스타일 묘사용이며 승률 예측에는 쓰지 않습니다.</p>
    {:else}
      <p class="muted small" style="margin:0">최근 1년 출전 맵이 10개 미만이라 속성을 계산하지 않았습니다.</p>
    {/if}
  </div>

  <h2>맵 × 요원 PP</h2>
  <div class="card" style="overflow-x:auto">
    <table>
      <thead>
        <tr><th>맵</th>{#each agents as [a]}<th>{cap(a)}</th>{/each}</tr>
      </thead>
      <tbody>
        {#each maps as m}
          <tr>
            <td>{cap(m)} <span class="muted small">{p.maps[m]?.rounds ?? 0}R</span></td>
            {#each agents as [a]}
              {@const v = p.grid[m]?.[a]}
              {@const w = p.mix[m]?.[a] ?? 0}
              <td class="num" style="background:{heat(v, p.pp - 4, p.pp + 4)}; opacity:{0.45 + 0.55 * Math.min(1, w * 2)}">{fx(v)}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
    <p class="muted small">색은 이 선수 평균 대비(파랑 −4 ~ 빨강 +4 PP). 셀이 흐릴수록 그 맵에서 해당 요원을 쓴 비중이 낮습니다. 맵·요원별 차이는 표본이 적어 약 90맵 분량의 데이터가 쌓여야 절반만큼 반영되도록 보수적으로 추정합니다.</p>
  </div>

  <h2>요원별</h2>
  <div class="list">
    {#each agents as [a, v]}
      <div class="row"><div class="grow">{cap(a)} <span class="muted small">{v.rounds}R</span></div><span class="pp">{fx(v.pp)}</span></div>
    {/each}
  </div>
{/if}
