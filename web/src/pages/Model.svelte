<script>
  import { app } from '../lib/store.svelte.js';
  import { REGION_LABEL, fx } from '../lib/format.js';

  const m = app.model;
  const bt = m.meta.backtest_map ?? {};
  const w = Object.entries(m.meta.diag?.weights ?? {});
  const wmax = Math.max(...w.map(([, v]) => Math.abs(v)), 1e-9);
  const LABEL = { kpr: '킬/라운드', dpr: '데스/라운드', apr: '어시/라운드', fkpr: '선킬/라운드', fdpr: '선데스/라운드', adr: 'ADR', kast: 'KAST' };
</script>

<h1>모델</h1>
<div class="card small">
  <div>기준일 <b>{m.meta.as_of}</b> · 데이터 {m.meta.data_from} ~ · 출처 {m.meta.source}</div>
  <div class="muted">생성 {m.meta.generated_at}</div>
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

<h2>축소 강도 (라운드 환산)</h2>
<div class="card small">
  {#each Object.entries(m.meta.diag?.shrinkage_k_rounds ?? {}) as [k, v]}
    <div>{k}: {fx(v, 0)}</div>
  {/each}
  <p class="muted">해당 수준의 추정치가 데이터 절반 신뢰를 얻는 데 필요한 라운드 수. 클수록 표본이 쌓여야 차이가 드러납니다.</p>
</div>
