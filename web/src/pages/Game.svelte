<script>
  // Match detail: per-map (set) win probabilities and the context behind them.
  import { app, persisted } from '../lib/store.svelte.js';
  import { scorelines, seriesOrdered, vetoMaps } from '../lib/engine.js';
  import { groupOf, resolveTeams } from '../lib/bracket.js';
  import { cap, fx, kst, pct } from '../lib/format.js';
  import Radar from '../lib/Radar.svelte';
  import { lockedFor } from '../lib/ledger.js';

  let { arg } = $props();
  let [bid, mid] = $derived((arg ?? '').split('/'));
  let br = $derived(app.brackets.find((b) => b.id === bid));
  let m = $derived(br?.matches.find((x) => x.id === mid));
  const locks = persisted('bracket-locks', {}).get();
  let teams = $derived(br && m ? resolveTeams(br, { ...(br.results ?? {}), ...(locks[br.id] ?? {}) })[m.id] : {});
  let A = $derived(teams.a), B = $derived(teams.b);
  let TA = $derived(app.engine.teams[A]), TB = $derived(app.engine.teams[B]);
  let bo = $derived(m?.best_of ?? 3);
  let played = $derived(!!br?.results?.[m?.id]);

  // map order: actual veto if published, otherwise the model's predicted veto
  let pmap = $derived(A && B ? Object.fromEntries(app.model.maps.map((mp) => [mp, app.engine.mapProb(A, B, mp)])) : {});
  let actualOrder = $derived(m?.veto?.order?.length ? m.veto.order : null);
  let order = $derived(actualOrder ?? (A && B ? vetoMaps(pmap, bo, true) : []));
  let ps = $derived(order.map((mp) => app.engine.mapProb(A, B, mp)));
  let pSeries = $derived(ps.length ? (actualOrder ? seriesOrdered(ps) : app.engine.series(A, B, bo).p) : null);
  let lines = $derived(ps.length ? Object.entries(scorelines(ps)) : []);

  // who picked each map (veto steps carry team tags)
  let pickOf = $derived(Object.fromEntries((m?.veto?.steps ?? []).filter((s) => s[1] !== 'ban').map((s) => [s[2], s[1] === 'remains' ? '결정' : `${s[0]} 픽`])));
  // pre-match map predictions from the accuracy check (played matches only)
  let preMatch = $derived((app.model.event_eval?.matches ?? []).find((x) => x.match_id === m?.vlr_id));
  let pre = $derived.by(() => {
    const e = preMatch;
    if (!e) return null;
    const flip = e.team_a !== A;
    return Object.fromEntries(e.maps.map((x) => [x.map, { p: flip ? 1 - x.p : x.p, win: flip ? 1 - x.win : x.win }]));
  });
  // prediction locked in the append-only ledger before the match started
  let ledgerEntry = $derived(br && m ? lockedFor(app.ledger, br.id, m) : null);
  let ledgerP = $derived(ledgerEntry && A && B ? (ledgerEntry.team_a === A ? ledgerEntry.p : ledgerEntry.team_b === A ? 1 - ledgerEntry.p : null) : null);
  // for finished matches show what was predicted BEFORE the match (no hindsight)
  let shownSeries = $derived(preMatch ? (preMatch.team_a === A ? preMatch.p : 1 - preMatch.p) : pSeries);

  const roster = (T) => (T?.roster ?? []).map((id) => ({ id, ...app.model.players[id] })).filter((p) => p.name);
  function playerOnMap(p, mp) {
    const mix = p.mix?.[mp] ?? p.mix?.['*'] ?? {};
    const agent = Object.entries(mix).sort((x, y) => y[1] - x[1])[0]?.[0];
    return { pp: p.maps?.[mp]?.pp ?? p.pp, rounds: p.maps?.[mp]?.rounds ?? 0, agent };
  }
  const rec = (T, mp) => T?.map_record?.[mp];
  const h2h = $derived((TA?.recent ?? []).filter((r) => r[1] === B).slice(-8).reverse());
  const form = (T) => (T?.recent ?? []).slice(-10);
  let axes = $derived(app.model.style_axes ?? []);
  const teamStyle = (T) => {
    const ps = roster(T).filter((p) => p.style);
    return ps.length ? Object.fromEntries(axes.map((a) => [a.key, ps.reduce((s, p) => s + p.style[a.key], 0) / ps.length])) : null;
  };
</script>

<a class="back" href="#/bracket">‹ 대진</a>
{#if !m}
  <p class="muted">경기를 찾을 수 없습니다.</p>
{:else}
  {@const g = groupOf(m)}
  <div style="--gc:{g.color}"><span class="gchip">{g.label}</span> <span class="muted small">{m.round} · Bo{bo} · {kst(m.time)}</span></div>
  {#if !(A && B)}
    <h1 style="margin-top:10px">대진 미정</h1>
    <p class="muted">앞 경기 결과가 나와야 팀이 정해집니다.</p>
  {:else}
    <h1 style="margin:10px 0 8px; font-size:22px">{A} <span class="muted">vs</span> {B}</h1>
    <div class="card">
      <div class="split">
        <div class="a" style="width:{Math.max(shownSeries * 100, 18)}%">{A} {pct(shownSeries)}</div>
        <div class="b" style="width:{Math.max((1 - shownSeries) * 100, 18)}%">{pct(1 - shownSeries)} {B}</div>
      </div>
      <p class="muted small" style="margin:8px 0 0">
        {#if played}종료 · 승자 <b>{br.results[m.id]}</b> · {preMatch ? '경기 전 예측' : '현재 모델 기준'}{:else}시리즈 승률{/if}
        · 맵 순서: {actualOrder ? '실제 밴픽' : '예상 밴픽(모델)'}
      </p>
      {#if played && ledgerP != null}
        <p class="small" style="margin:4px 0 0">🔒 기록된 예측 ({kst(ledgerEntry.recorded_at)}): {A} {pct(ledgerP)}</p>
      {/if}
      <div style="display:flex; gap:6px; margin-top:10px; flex-wrap:wrap" hidden={played}>
        {#each lines as [s, q]}
          <span class="badge" style="color:{+s[0] > +s[2] ? 'var(--accent)' : 'var(--muted)'}">{A} {s} · {pct(q)}</span>
        {/each}
      </div>
    </div>

    <h2>세트별 예측</h2>
    {#each order as mp, i}
      {@const p = pre?.[mp]?.p ?? ps[i]}
      {@const ra = rec(TA, mp)}
      {@const rb = rec(TB, mp)}
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:baseline">
          <div><b style="font-size:17px">세트 {i + 1} · {cap(mp)}</b> <span class="muted small">{pickOf[mp] ?? (actualOrder ? '' : i === order.length - 1 ? '결정(예상)' : '픽(예상)')}</span></div>
          {#if pre?.[mp]}
            {@const ok = (pre[mp].p > 0.5) === (pre[mp].win === 1)}
            <span class="small" style="color:{ok ? 'var(--good)' : 'var(--bad)'}; text-align:right">{ok ? '○' : '×'} <b>{pre[mp].win === 1 ? A : B} 승</b></span>
          {/if}
        </div>
        {#if pre?.[mp]}<div class="muted small" style="margin-top:4px">경기 전 예측</div>{/if}
        <div class="split" style="margin-top:6px; height:24px">
          <div class="a" style="width:{Math.max(p * 100, 16)}%">{pct(p)}</div>
          <div class="b" style="width:{Math.max((1 - p) * 100, 16)}%">{pct(1 - p)}</div>
        </div>
        <table style="margin-top:8px">
          <thead><tr><th></th><th>{A}</th><th>{B}</th></tr></thead>
          <tbody>
            <tr><td>맵 팀 PP</td><td class="num">{fx(500 + 1000 * (TA?.theta?.[mp] ?? 0), 0)}</td><td class="num">{fx(500 + 1000 * (TB?.theta?.[mp] ?? 0), 0)}</td></tr>
            <tr><td>최근 1년 전적</td><td class="num">{ra ? `${ra[1]}승 ${ra[0] - ra[1]}패` : '–'}</td><td class="num">{rb ? `${rb[1]}승 ${rb[0] - rb[1]}패` : '–'}</td></tr>
            <tr><td>라운드 승률</td><td class="num">{ra ? pct(ra[2] / ra[3]) : '–'}</td><td class="num">{rb ? pct(rb[2] / rb[3]) : '–'}</td></tr>
          </tbody>
        </table>
        <details style="margin-top:6px">
          <summary class="small muted">선수별 {cap(mp)} PP · 예상 요원</summary>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:6px">
            {#each [TA, TB] as T}
              <div class="small" style="min-width:0">
                {#each roster(T) as pl}
                  {@const v = playerOnMap(pl, mp)}
                  <a href={`#/player/${pl.id}`} style="display:flex; justify-content:space-between; color:inherit; text-decoration:none; padding:2px 0">
                    <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap">{pl.name} <span class="muted">{cap(v.agent ?? '')}</span></span>
                    <span class="num">{fx(v.pp)}</span>
                  </a>
                {/each}
              </div>
            {/each}
          </div>
        </details>
      </div>
    {/each}
    <p class="muted small">맵 승률 = 출전 로스터 5명의 해당 맵 PP(예상 요원 기준) 합 차이 + 지역 보정. 팀의 맵 전적·최근 폼·플레이 스타일은 검증 결과 예측을 개선하지 않아 참고 정보로만 표시합니다.</p>

    {#if teamStyle(TA) && teamStyle(TB)}
      <h2>속성 비교 (로스터 평균)</h2>
      <div class="card">
        <Radar {axes} series={[{ values: teamStyle(TA), color: 'var(--accent)', label: A }, { values: teamStyle(TB), color: 'var(--g-a)', label: B }]} />
      </div>
    {/if}

    <h2>상대 전적 (최근 1년, 맵 단위)</h2>
    <div class="card small">
      {#if h2h.length}
        {#each h2h as r}
          <div style="display:flex; justify-content:space-between; padding:2px 0">
            <span class="muted">{r[0]}</span><span>{cap(r[2])}</span>
            <b style="color:{r[3] > r[4] ? 'var(--good)' : 'var(--bad)'}">{A} {r[3]}:{r[4]}</b>
          </div>
        {/each}
      {:else}<span class="muted">최근 1년 맞대결 기록이 없습니다.</span>{/if}
    </div>

    <h2>최근 10맵 흐름</h2>
    <div class="card small">
      {#each [[A, TA], [B, TB]] as [n, T]}
        <div style="display:flex; align-items:center; gap:6px; margin:4px 0">
          <span style="width:90px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">{n}</span>
          {#each form(T) as r}
            <span title="{r[0]} vs {r[1]} {r[2]} {r[3]}:{r[4]}" style="width:14px; height:14px; border-radius:3px; background:{r[3] > r[4] ? 'var(--good)' : 'var(--bad)'}; opacity:0.85"></span>
          {/each}
        </div>
      {/each}
      <p class="muted" style="margin:6px 0 0">왼쪽이 오래된 경기, 초록 = 맵 승.</p>
    </div>
  {/if}
{/if}
