<script>
  import { app } from '../lib/store.svelte.js';
  import { REGION_LABEL, fx } from '../lib/format.js';

  let region = $state('ALL');
  let q = $state('');
  const norm = (x) => (x ?? '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
  let teams = $derived(app.model.teams
    .map((t, i) => ({ ...t, rank: i + 1 }))
    .filter((t) => (region === 'ALL' || t.region === region) && norm(t.name).includes(norm(q.trim()))));
</script>

<h1>팀 파워 랭킹</h1>
<input class="search" type="search" placeholder="팀 검색" bind:value={q} id="team-search" autocomplete="off" />
<div class="chips">
  {#each ['ALL', 'AMER', 'EMEA', 'PAC', 'CN'] as r}
    <button class="chip" class:on={region === r} onclick={() => (region = r)}>{r === 'ALL' ? '전체' : REGION_LABEL[r]}</button>
  {/each}
</div>
<p class="muted small">팀 PP = 현재 로스터 5명 PP 합(맵 풀 평균, 지역 보정 포함). 500 = 평균 팀.</p>
<div class="list">
  {#each teams as t}
    <a class="row" href={`#/team/${encodeURIComponent(t.name)}`}>
      <span class="rank">{t.rank}</span>
      <div class="grow">
        <div class="title">{t.name}</div>
        <span class="badge {t.region}">{t.region}</span>
      </div>
      <span class="pp">{fx(t.pp, 0)}</span>
    </a>
  {/each}
</div>
