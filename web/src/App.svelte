<script>
  import { app, loadModel } from './lib/store.svelte.js';
  import Teams from './pages/Teams.svelte';
  import Team from './pages/Team.svelte';
  import Players from './pages/Players.svelte';
  import Player from './pages/Player.svelte';
  import Match from './pages/Match.svelte';
  import Bracket from './pages/Bracket.svelte';
  import Model from './pages/Model.svelte';

  loadModel();

  const tabs = [
    { id: 'teams', label: '팀', icon: 'M4 6h16M4 12h16M4 18h10' },
    { id: 'players', label: '선수', icon: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0' },
    { id: 'match', label: '매치', icon: 'M5 5l14 14M19 5L5 19' },
    { id: 'bracket', label: '대진', icon: 'M4 5h5v5H4zM4 14h5v5H4zM9 7.5h3v9H9M12 12h4M16 9.5h4v5h-4z' },
    { id: 'model', label: '모델', icon: 'M4 19V9m6 10V5m6 14v-7m4 7H3' },
  ];
  const tabOf = { team: 'teams', player: 'players' };
  let active = $derived(tabOf[app.route.page] ?? app.route.page);
</script>

<main>
  {#if app.error}
    <div class="card">데이터를 불러오지 못했습니다: {app.error}</div>
  {:else if !app.model}
    <p class="muted">불러오는 중…</p>
  {:else}
    {#if app.model.meta.source === 'synthetic'}
      <div class="banner">합성(가짜) 데이터로 만든 데모입니다. 실제 vlr.gg 데이터가 수집되면 교체됩니다.</div>
    {/if}
    {#if app.route.page === 'teams'}<Teams />
    {:else if app.route.page === 'team'}<Team name={app.route.arg} />
    {:else if app.route.page === 'players'}<Players />
    {:else if app.route.page === 'player'}<Player id={app.route.arg} />
    {:else if app.route.page === 'match'}<Match />
    {:else if app.route.page === 'bracket'}<Bracket />
    {:else if app.route.page === 'model'}<Model />
    {:else}<Teams />{/if}
  {/if}
</main>

<nav class="tabbar">
  {#each tabs as t}
    <a href={`#/${t.id}`} class:on={active === t.id}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d={t.icon} /></svg>
      {t.label}
    </a>
  {/each}
</nav>
