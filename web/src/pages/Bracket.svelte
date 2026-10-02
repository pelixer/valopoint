<script>
  import { app, persisted } from '../lib/store.svelte.js';
  import { simulateBracket } from '../lib/engine.js';
  import { fx, kst, kstShort, pct } from '../lib/format.js';
  import { groupOf, groupTable, resolveTeams } from '../lib/bracket.js';

  const store = persisted('bracket-locks', {});
  let idx = $state(0);
  let br = $derived(app.brackets[idx]);
  // official results from vlr.gg + my own what-if locks
  let mine = $state(store.get());
  let locked = $derived(br ? { ...(br.results ?? {}), ...(mine[br.id] ?? {}) } : {});
  let full = $derived(br?.kind === 'full' || br?.kind === undefined);
  let sim = $derived(br && br.matches.length ? simulateBracket(app.engine, br, locked, 20000) : null);
  let ev = $derived(app.model.event_eval);
  // pre-match predictions (from the accuracy check) for matches already played
  let preMatch = $derived(Object.fromEntries((ev?.matches ?? []).map((m) => [m.match_id, m])));
  function preP(m, team) {
    const e = preMatch[m.vlr_id];
    if (!e) return null;
    return team === e.team_a ? e.p : 1 - e.p;
  }

  let fixed = $derived(br ? resolveTeams(br, locked) : {});
  const view = persisted('bracket-view', { mode: 'time', filter: 'ALL' });
  let mode = $state(view.get().mode);
  let filter = $state(view.get().filter);
  $effect(() => view.set({ mode, filter }));
  let groups = $derived.by(() => {
    const seen = new Map();
    for (const m of br?.matches ?? []) { const g = groupOf(m); if (!seen.has(g.key)) seen.set(g.key, g); }
    return [...seen.values()];
  });
  let visible = $derived((br?.matches ?? []).filter((m) => filter === 'ALL' || groupOf(m).key === filter));

  // matches in the order they are (or were) played, grouped by KST date
  const dayKey = (iso) => iso ? new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: 'long', day: 'numeric', weekday: 'short' }).format(new Date(iso)) : '일정 미정';
  let rounds = $derived.by(() => {
    const ms = [...visible].sort((x, y) => (x.time ?? '9999').localeCompare(y.time ?? '9999'));
    const g = [];
    for (const m of ms) {
      const d = dayKey(m.time);
      const last = g.at(-1);
      if (last && last.round === d) last.items.push(m);
      else g.push({ round: d, items: [m] });
    }
    return g;
  });

  function lock(mid, team) {
    if (br.results?.[mid]) return;
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
  const played = (m) => !!br.results?.[m.id];
</script>

<h1>대진표</h1>
{#if !app.brackets.length}
  <p class="muted">아직 수집된 대진이 없습니다. 매일 00시·12시(KST)에 진행 중인 대회의 대진을 불러옵니다.</p>
{:else}
  {#if app.brackets.length > 1}
    <select bind:value={idx} style="margin-bottom:10px">
      {#each app.brackets as b, i}<option value={i}>{b.name}</option>{/each}
    </select>
  {/if}
  <div class="card small">
    <b>{br.name}</b>
    <div class="muted">대진 갱신 {kst(app.bracketsAt)} · 완료 {Object.keys(br.results ?? {}).length}/{br.matches.length}경기 · 20,000회 시뮬레이션</div>
    {#if br.assumed?.length}<div class="muted">플레이오프 대진({br.assumed.join(', ')})은 조별 순위 기반 추정이며, 확정되면 자동으로 바뀝니다.</div>{/if}
  </div>

  {#if full && sim}
    <h2>우승 확률</h2>
    <div class="list">
      {#each top(sim.champion, 16) as [t, p]}
        <div class="row">
          <div class="grow title">{t}</div>
          <div style="width:40%"><div class="bar"><span style="width:{p * 100}%"></span></div></div>
          <span class="num" style="width:52px; text-align:right">{pct(p, 1)}</span>
        </div>
      {/each}
    </div>
  {/if}

  <h2>경기 <button class="btn small" style="float:right" onclick={reset}>내 가정 초기화</button></h2>
  <div style="display:flex; gap:8px; align-items:center; margin-bottom:8px; flex-wrap:wrap">
    <div class="seg">
      <button class:on={mode === 'time'} onclick={() => (mode = 'time')}>시간순</button>
      <button class:on={mode === 'group'} onclick={() => (mode = 'group')}>그룹별</button>
    </div>
  </div>
  <div class="chips">
    <button class="chip" class:on={filter === 'ALL'} onclick={() => (filter = 'ALL')}>전체</button>
    {#each groups as g}
      <button class="chip" class:on={filter === g.key} style="--gc:{g.color}" onclick={() => (filter = g.key)}>
        <span class="gchip" style="background:transparent; padding:0">{g.label}</span>
      </button>
    {/each}
  </div>
  <p class="muted small">팀 버튼을 누르면 그 팀이 이긴다고 가정해 이후 확률을 다시 계산합니다(내 기기에만 저장). "세트별 예측"을 누르면 맵별 상세로 이동합니다.</p>

  {#snippet matchCard(m)}
    {@const f = fixed[m.id]}
    {@const g = groupOf(m)}
    <div class="card mcard" style="--gc:{g.color}">
      <div class="small" style="display:flex; gap:6px; align-items:center; flex-wrap:wrap">
        <span class="gchip">{g.label}</span>
        <span class="muted">{kstShort(m.time)} · {m.round} · Bo{m.best_of ?? 3}{played(m) ? ' · 종료' : ''}</span>
      </div>
      {#if f.a && f.b}
        {@const p = app.engine.series(f.a, f.b, m.best_of ?? 3).p}
        <div style="display:flex; gap:8px; margin-top:6px">
          {#each [[f.a, p], [f.b, 1 - p]] as [t, q]}
            <button class="btn" style="flex:1; min-width:0; text-align:left; {locked[m.id] === t ? 'border-color:var(--accent); background:#3a1f25' : ''}"
              onclick={() => lock(m.id, t)} disabled={played(m)}>
              <div style="font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">{t}</div>
              <div class="muted small">
                {#if played(m)}{locked[m.id] === t ? '승' : '패'}{#if preP(m, t) != null} · 경기 전 예측 {pct(preP(m, t))}{/if}
                {:else if locked[m.id]}{locked[m.id] === t ? '승 (가정)' : '패 (가정)'}
                {:else}{pct(q)}{/if}
              </div>
            </button>
          {/each}
        </div>
      {:else if sim}
        <div class="small" style="margin-top:6px">
          <span class="muted">진출 예상:</span>
          {#each top(sim.slot[m.id], 4) as [t, q], i}{i ? ', ' : ' '}{t} {pct(q)}{/each}
        </div>
      {/if}
      <a class="detail-link" href={`#/game/${br.id}/${m.id}`}>세트별 예측 ›</a>
    </div>
  {/snippet}

  {#if mode === 'time'}
    {#each rounds as r}
      <div class="dayhead">{r.round}</div>
      {#each r.items as m}{@render matchCard(m)}{/each}
    {/each}
  {:else}
    {#each groups.filter((g) => filter === 'ALL' || g.key === filter) as g}
      {@const items = br.matches.filter((m) => groupOf(m).key === g.key).sort((x, y) => (x.time ?? '9999').localeCompare(y.time ?? '9999'))}
      {@const table = /^[A-H]$/.test(g.key) ? groupTable(br, g.key) : []}
      <section class="gsection" style="--gc:{g.color}">
        <div class="gtitle">{g.label}</div>
        {#if table.length}
          <div class="small" style="display:flex; flex-wrap:wrap; gap:6px 14px; margin:0 2px 10px">
            {#each table as [t, r]}<span><b>{t}</b> <span class="muted">{r.w}승 {r.l}패</span></span>{/each}
          </div>
        {/if}
        {#each items as m}{@render matchCard(m)}{/each}
      </section>
    {/each}
  {/if}
{/if}

{#if ev?.matches?.length}
  <h2>예측 검증 · {ev.name}</h2>
  <div class="card small">
    <p class="muted" style="margin-top:0">각 팀의 첫 경기는 대회 전 데이터(지역리그 등)만으로, 두 번째 경기부터는 그 전까지의 챔스 결과까지 넣어 다시 학습한 모델로 경기 전에 예측했을 때의 성적입니다.</p>
    <table>
      <thead><tr><th>구분</th><th>경기</th><th>적중</th><th>Log loss</th></tr></thead>
      <tbody>
        {#each [['전체 (시리즈)', ev.summary.series_all], ['팀별 첫 경기', ev.summary.series_first_match], ['두 번째 경기부터', ev.summary.series_later], ['맵 단위', ev.summary.maps], ['맵 단위 · Elo 비교', ev.summary.maps_elo]] as [label, s]}
          <tr><td>{label}</td><td class="num">{s.n}</td><td class="num">{s.n ? pct(s.accuracy) : '–'}</td><td class="num">{s.n ? fx(s.log_loss, 3) : '–'}</td></tr>
        {/each}
      </tbody>
    </table>
    <p class="muted">표본이 작아 적중률은 운의 영향이 큽니다. Log loss(낮을수록 좋음, 동전 0.693)가 더 믿을 만한 지표입니다.</p>
  </div>
  <div class="list">
    {#each ev.matches as m}
      <div class="row small">
        <span style="width:18px; color:{m.correct ? 'var(--good)' : 'var(--bad)'}; font-weight:700">{m.correct ? '○' : '×'}</span>
        <div class="grow">
          <div><b>{m.team_a}</b> {m.score} <b>{m.team_b}</b></div>
          <div class="muted">{m.stage} · 예측 {m.p >= 0.5 ? m.team_a : m.team_b} 승 {pct(Math.max(m.p, 1 - m.p))} · {m.basis_a === 'pre-event' || m.basis_b === 'pre-event' ? '대회 전 기준' : '대회 결과 반영'}</div>
        </div>
      </div>
    {/each}
  </div>
{/if}
