<script>
  import { app } from '../lib/store.svelte.js';
  import { ROLE_LABEL, cap, fx, heat } from '../lib/format.js';
  import Radar from '../lib/Radar.svelte';
  import { badges, buildContext } from '../lib/profile.js';

  let { id } = $props();
  let p = $derived(app.model.players[id]);
  let agents = $derived(p ? Object.entries(p.agents).sort((a, b) => b[1].rounds - a[1].rounds) : []);
  let maps = $derived(p ? Object.keys(p.grid) : []);
  let axes = $derived(app.model.style_axes ?? []);
  let ctx = $derived(buildContext(app.model, app.brackets));
  let tags = $derived(p ? badges({ id, ...p }, ctx) : []);
  let prof = $derived(p?.profile ?? {});
  let ranks = $derived.by(() => {
    if (!p) return [];
    const P = ctx.byPP;
    const r = (f) => P.filter(f).findIndex((x) => x.id === id) + 1;
    return [['전체', r(() => true), P.length], [ROLE_LABEL[p.role] ?? p.role, r((x) => x.role === p.role), P.filter((x) => x.role === p.role).length],
      [p.region, r((x) => x.region === p.region), P.filter((x) => x.region === p.region).length]];
  });
  // timeline chart: one point per event (PP of that event), international events highlighted
  const TW = 340, TH = 150, PL = 30, PB = 22;
  let tl = $derived(prof.timeline ?? []);
  let tlY = $derived.by(() => {
    const v = tl.map((e) => e[3]);
    const lo = Math.min(80, ...v) - 5, hi = Math.max(130, ...v) + 5;
    return { lo, hi, y: (x) => TH - PB - ((x - lo) / (hi - lo)) * (TH - PB - 8) };
  });
  const tlX = (i, n) => PL + (n <= 1 ? (TW - PL - 10) / 2 : (i / (n - 1)) * (TW - PL - 10));
  const sgn = (x) => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(1)}`;
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
    <div style="margin-top:6px"><span class="muted">PP</span> <span class="pp" style="font-size:24px">{fx(p.pp)}</span>
      <span class="muted small" style="margin-left:6px">{#each ranks as [lbl, r, n], i}{i ? ' · ' : ''}{lbl} {r}위/{n}{/each}</span>
    </div>
    {#if tags.length}
      <div class="tags" style="margin-top:8px">
        {#each tags as t}<span class="tag {t.tone}">{t.icon} {t.label}</span>{/each}
      </div>
    {/if}
  </div>

  <h2>폼 · 커리어</h2>
  <div class="grid2">
    <div class="card stat">
      <div class="muted small">최근 60일 폼</div>
      {#if prof.form}
        <div class="big">{prof.form.recent.toFixed(1)} <span class="small" style="color:{prof.form.delta >= 0 ? 'var(--good)' : 'var(--bad)'}">{sgn(prof.form.delta)}</span></div>
        <div class="muted small">이전 {prof.form.before.toFixed(1)} · {prof.form.maps}맵</div>
      {:else}<div class="muted small">최근 경기 없음</div>{/if}
    </div>
    <div class="card stat">
      <div class="muted small">꾸준함 (최근 1년)</div>
      {#if prof.steady}
        <div class="big" style="font-size:18px">{prof.steady.rel ? `기복 ${Math.abs((1 - prof.steady.rel) * 100).toFixed(0)}% ${prof.steady.rel <= 1 ? '적음' : '많음'}` : fx(prof.steady.sd, 0)}</div>
        <div class="muted small">같은 역할 평균 대비 · 하위 25% 경기 {prof.steady.floor.toFixed(0)}</div>
      {:else}<div class="muted small">20맵 미만</div>{/if}
    </div>
    <div class="card stat">
      <div class="muted small">국제전 (최근 2년)</div>
      {#if prof.intl}
        <div class="big">{prof.intl.pp.toFixed(1)} <span class="small" style="color:{prof.intl.big_stage >= 0 ? 'var(--good)' : 'var(--bad)'}">{sgn(prof.intl.big_stage)}</span></div>
        <div class="muted small">{prof.intl.events}회 · {prof.intl.map_wins}승 {prof.intl.maps - prof.intl.map_wins}패 · 초록/빨강 = 리그 대비</div>
      {:else}<div class="muted small">출전 기록 없음</div>{/if}
    </div>
    <div class="card stat">
      <div class="muted small">{prof.current ? app.model.meta.current_event?.name?.replace(/^Valorant /, '') : '최근 지역리그'}</div>
      {#if prof.current}
        <div class="big">{prof.current.pp.toFixed(1)}</div>
        <div class="muted small">{prof.current.maps}맵 {prof.current.map_wins}승 {prof.current.maps - prof.current.map_wins}패</div>
      {:else if prof.league}
        <div class="big">{prof.league.pp.toFixed(1)}</div>
        <div class="muted small">{prof.league.event} · {prof.league.maps}맵 {prof.league.map_wins}승</div>
      {:else}<div class="muted small">–</div>{/if}
    </div>
  </div>
  {#if prof.intl?.list?.length}
    <p class="muted small" style="margin:4px 0 0">국제전 출전: {prof.intl.list.join(' · ')}</p>
  {/if}

  {#if tl.length}
    <h2>대회별 퍼포먼스</h2>
    <div class="card">
      <svg viewBox="0 0 {TW} {TH}" style="width:100%; display:block">
        {#each [80, 100, 120, 140].filter((t) => t > tlY.lo && t < tlY.hi) as t}
          <line x1={PL} x2={TW - 6} y1={tlY.y(t)} y2={tlY.y(t)} stroke="var(--border)" stroke-dasharray={t === 100 ? '' : '3 3'} />
          <text x={PL - 4} y={tlY.y(t) + 3} text-anchor="end" font-size="9" fill="var(--muted)">{t}</text>
        {/each}
        <polyline fill="none" stroke="var(--muted)" stroke-width="1.2" points={tl.map((e, i) => `${tlX(i, tl.length)},${tlY.y(e[3])}`).join(' ')} />
        {#each tl as e, i}
          <circle cx={tlX(i, tl.length)} cy={tlY.y(e[3])} r={2.5 + Math.min(4, e[2] / 8)} fill={e[4] ? 'var(--accent)' : 'var(--surface-2)'} stroke={e[4] ? 'var(--accent)' : 'var(--muted)'} />
        {/each}
        <line x1={PL} x2={TW - 6} y1={tlY.y(p.pp)} y2={tlY.y(p.pp)} stroke="var(--accent)" stroke-opacity="0.5" stroke-dasharray="2 4" />
      </svg>
      <table class="small" style="margin-top:6px">
        <tbody>
          {#each [...tl].reverse() as e}
            <tr>
              <td style="text-align:left">{#if e[4]}<span style="color:var(--accent)">●</span>{/if} {e[0]}</td>
              <td class="num muted">{e[1].slice(0, 7)}</td>
              <td class="num">{e[5]}승 {e[2] - e[5]}패</td>
              <td class="num"><b>{e[3].toFixed(0)}</b></td>
            </tr>
          {/each}
        </tbody>
      </table>
      <p class="muted small" style="margin-bottom:0">대회별 맵 퍼포먼스(상대 보정, PP 척도). 빨간 점 = 국제전, 점 크기 = 맵 수, 점선 = 현재 PP. 대회 하나는 표본이 작아 흔들림이 큽니다.</p>
    </div>
  {/if}

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
