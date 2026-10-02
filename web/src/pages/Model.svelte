<script>
  import { app } from '../lib/store.svelte.js';
  import { REGION_LABEL, fx, kst, kstShort, pct } from '../lib/format.js';
  import { lockedResults, summarize } from '../lib/ledger.js';

  const m = app.model;
  const bt = m.meta.backtest_map ?? {};
  const w = Object.entries(m.meta.diag?.weights ?? {});
  const wmax = Math.max(...w.map(([, v]) => Math.abs(v)), 1e-9);
  const rel = m.calib?.reliability ?? [];
  // reliability chart geometry: predicted 50–100% (x) vs actual 30–100% (y)
  const W = 300, H = 220, PADL = 34, PADB = 26;
  const X = (p) => PADL + ((p - 0.5) / 0.5) * (W - PADL - 8);
  const Y = (p) => H - PADB - ((p - 0.3) / 0.7) * (H - PADB - 8);
  const rmax = Math.max(...rel.map((b) => b.n), 1);
  let locked = $derived(lockedResults(app.ledger, app.brackets));
  let sum = $derived(summarize(locked));
  let pending = $derived.by(() => {
    const done = new Set(locked.map((r) => r.bracket + '/' + r.match));
    const last = new Map();
    for (const e of app.ledger ?? []) if (!done.has(e.bracket + '/' + e.match)) last.set(e.bracket + '/' + e.match, e);
    return [...last.values()].filter((e) => !e.match_time || Date.parse(e.match_time) > Date.now())
      .sort((a, b) => Date.parse(a.match_time ?? 0) - Date.parse(b.match_time ?? 0));
  });
  const LABEL = { kpr: '킬/라운드', dpr: '데스/라운드', apr: '어시/라운드', fkpr: '선킬/라운드', fdpr: '선데스/라운드', adr: 'ADR', kast: 'KAST' };
</script>

<h1>모델</h1>
<div class="card small">
  <div>기준일 <b>{m.meta.as_of}</b> · 데이터 {m.meta.data_from} ~ · 출처 {m.meta.source}</div>
  <div class="muted">갱신 {kst(m.meta.generated_at)}</div>
  {#if m.meta.live_events?.length}<div>진행 중 국제전 반영: {m.meta.live_events.join(', ')}</div>{/if}
</div>

<h2>지역 보정</h2>
<div class="card">
  <table>
    <thead><tr><th>지역</th><th>선수당 PP 보정</th><th>국제전 결과 γ</th></tr></thead>
    <tbody>
      {#each Object.entries(m.regions) as [r, v]}
        <tr><td><span class="badge {r}">{r}</span> {REGION_LABEL[r]}</td><td class="num">{fx(v.offset_pp)}</td><td class="num">{fx(v.gamma, 3)}</td></tr>
      {/each}
    </tbody>
  </table>
  <p class="muted small">PP 보정: 국제전 stat으로 추정한 지역 수준(리그 간 환산). γ: stat으로 설명되지 않는 국제전 승패 잔차(최근 2년, 시간 가중). 보정 기울기 β = {fx(m.calib.beta, 3)}</p>
</div>

<h2>학습된 stat 가중치</h2>
<div class="card">
  {#each w as [k, v]}
    <div style="display:flex; align-items:center; gap:8px; margin:4px 0">
      <div style="width:96px" class="small">{LABEL[k] ?? k}</div>
      <div class="grow" style="flex:1"><div class="bar"><span style="width:{(Math.abs(v) / wmax) * 100}%; background:{v < 0 ? 'var(--bad)' : 'var(--good)'}"></span></div></div>
      <span class="num small" style="width:64px; text-align:right">{v.toFixed(4)}</span>
    </div>
  {/each}
  <p class="muted small">역할군 내 표준화 후, 맵 라운드 승률에 대한 회귀로 추정한 기여도.</p>
</div>

<h2>백테스트 (국제전 맵, walk-forward)</h2>
<div class="card">
  <table>
    <tbody>
      <tr><td>평가 맵 수</td><td class="num">{bt.n ?? '–'}</td></tr>
      <tr><td>Log loss (동전 0.693)</td><td class="num">{fx(bt.log_loss, 4)}</td></tr>
      <tr><td>Brier (동전 0.25)</td><td class="num">{fx(bt.brier, 4)}</td></tr>
      <tr><td>정확도</td><td class="num">{bt.accuracy != null ? (bt.accuracy * 100).toFixed(1) + '%' : '–'}</td></tr>
    </tbody>
  </table>
</div>

<h2>보정 그래프 (예측 확률 vs 실제 승률)</h2>
<div class="card">
  {#if rel.length}
    <svg viewBox="0 0 {W} {H}" style="width:100%; max-width:420px; display:block; margin:0 auto">
      {#each [0.3, 0.5, 0.7, 0.9] as t}
        <line x1={PADL} x2={W - 8} y1={Y(t)} y2={Y(t)} stroke="var(--border)" />
        <text x={PADL - 4} y={Y(t) + 3} text-anchor="end" font-size="9" fill="var(--muted)">{t * 100}%</text>
      {/each}
      {#each [0.5, 0.6, 0.7, 0.8, 0.9, 1] as t}
        <text x={X(t)} y={H - PADB + 13} text-anchor={t === 1 ? 'end' : 'middle'} font-size="9" fill="var(--muted)">{t * 100}%</text>
      {/each}
      <line x1={X(0.5)} y1={Y(0.5)} x2={X(1)} y2={Y(1)} stroke="var(--muted)" stroke-dasharray="4 3" />
      <polyline fill="none" stroke="var(--accent)" stroke-width="1.5" points={rel.map((b) => `${X(b.pred)},${Y(b.actual)}`).join(' ')} />
      {#each rel as b}
        <circle cx={X(b.pred)} cy={Y(b.actual)} r={3 + 6 * Math.sqrt(b.n / rmax)} fill="var(--accent)" fill-opacity="0.35" stroke="var(--accent)" />
      {/each}
      <text x={(PADL + W) / 2} y={H - 2} text-anchor="middle" font-size="9" fill="var(--muted)">예측한 유력팀 승률</text>
    </svg>
    <table class="small" style="margin-top:8px">
      <thead><tr><th>예측 구간</th><th>맵 수</th><th>평균 예측</th><th>실제</th></tr></thead>
      <tbody>
        {#each rel as b}
          <tr><td>{pct(b.lo)}–{pct(b.hi)}</td><td class="num">{b.n}</td><td class="num">{pct(b.pred, 1)}</td><td class="num">{pct(b.actual, 1)}</td></tr>
        {/each}
      </tbody>
    </table>
    <p class="muted small">국제전 맵을 walk-forward로(해당 경기 이전 데이터만으로) 예측한 결과입니다. 점이 점선(완벽 보정) 위에 있으면 70%라고 한 경기를 실제로 70% 이깁니다. 점 크기 = 표본 수.</p>
  {:else}
    <p class="muted">다음 모델 갱신(00시) 후 표시됩니다.</p>
  {/if}
</div>

<h2>기록된 경기 전 예측</h2>
<div class="card">
  {#if sum}
    <div>적중 <b>{sum.correct}/{sum.n}</b> ({pct(sum.correct / sum.n)}) · 모델 기대 {fx(sum.expected, 1)} · Log loss {fx(sum.logLoss, 3)} · Brier {fx(sum.brier, 3)}</div>
    <table class="small" style="margin-top:8px">
      <tbody>
        {#each [...locked].reverse() as r}
          <tr>
            <td>{kstShort(r.match_time)}</td>
            <td style="text-align:left">{r.p >= 0.5 ? r.team_a : r.team_b} <span class="muted">{pct(Math.max(r.p, 1 - r.p))}</span></td>
            <td style="color:{r.correct ? 'var(--good)' : 'var(--bad)'}">{r.correct ? '○' : '×'} {r.winner}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <p class="muted">아직 기록된 예측으로 끝난 경기가 없습니다.</p>
  {/if}
  {#if pending.length}
    <div class="small" style="margin-top:10px"><b>기록 중 (경기 전)</b></div>
    <table class="small">
      <tbody>
        {#each pending as e}
          <tr><td>{kstShort(e.match_time)}</td><td style="text-align:left">{e.team_a} vs {e.team_b}</td><td class="num">{pct(e.p)}</td><td class="muted">{kstShort(e.recorded_at)} 기록</td></tr>
        {/each}
      </tbody>
    </table>
  {/if}
  <p class="muted small">00시·12시(KST) 갱신 때마다 아직 시작 전인 경기의 예측을 시각과 함께 추가만 하는 파일(ledger.json)에 남깁니다. 경기가 끝나면 시작 직전 마지막 기록을 그 경기의 예측으로 채점합니다. 기존 기록은 수정하지 않으며, 저장소의 Git 이력이 그 증거입니다.</p>
</div>

{#if m.veto_model}
  <h2>밴픽 모델</h2>
  <div class="card small">
    <div>반영 기간: {m.veto_model.events.join(', ')} · 밴픽 {m.veto_model.n}건</div>
    <p class="muted">진행 중인 대회 + 직전 2개 시즌 구간(지역리그 같은 스테이지는 한 구간)만 사용합니다. 각 팀의 밴/픽 횟수를 리그 전체 경향 쪽으로 축소(사전 {m.veto_model.prior}회분)해 밴픽 순서를 모두 따집니다. 검증(스테이지 2·챔스 181경기): 실제 플레이된 맵이 예상 세트 순서에 든 비율 55%(스탯 기반 그리디 44%), 시리즈 log loss 0.6678 → 0.6671.</p>
  </div>
{/if}

<h2>축소 강도 (라운드 환산)</h2>
<div class="card small">
  {#each Object.entries(m.meta.diag?.shrinkage_k_rounds ?? {}) as [k, v]}
    <div>{k}: {fx(v, 0)}</div>
  {/each}
  <p class="muted">해당 수준의 추정치가 데이터 절반 신뢰를 얻는 데 필요한 라운드 수. 클수록 표본이 쌓여야 차이가 드러납니다.</p>
</div>
