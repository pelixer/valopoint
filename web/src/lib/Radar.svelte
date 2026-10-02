<script>
  // N-gon radar ("attribute graph"): one vertex per axis, so 6 axes -> hexagon,
  // 10 axes -> decagon. Values are 0-100 percentiles.
  let { axes = [], series = [], size = 300 } = $props();
  // series: [{ values: {key: 0-100}, color, label, dashed? }]

  const pad = 52;
  let n = $derived(axes.length);
  let r = $derived(size / 2 - pad);
  let c = $derived(size / 2);
  const angle = (i) => -Math.PI / 2 + (2 * Math.PI * i) / n;
  const pt = (i, v) => [c + (r * v * Math.cos(angle(i))) / 100, c + (r * v * Math.sin(angle(i))) / 100];
  const poly = (vals) => axes.map((a, i) => pt(i, Math.max(0, Math.min(100, vals?.[a.key] ?? 0))).join(',')).join(' ');
  const ring = (v) => axes.map((_, i) => pt(i, v).join(',')).join(' ');
  function anchor(i) {
    const x = Math.cos(angle(i));
    return x > 0.25 ? 'start' : x < -0.25 ? 'end' : 'middle';
  }
</script>

{#if n >= 3}
  <svg viewBox="0 0 {size} {size}" width="100%" style="max-width:{size}px; display:block; margin:0 auto" role="img"
    aria-label="속성 그래프: {axes.map((a) => `${a.label} ${Math.round(series[0]?.values?.[a.key] ?? 0)}`).join(', ')}">
    {#each [25, 50, 75, 100] as v}
      <polygon points={ring(v)} fill="none" stroke="var(--border)" stroke-width={v === 50 ? 1.2 : 0.8}
        stroke-dasharray={v === 50 ? '3 3' : ''} />
    {/each}
    {#each axes as _, i}
      {@const [x, y] = pt(i, 100)}
      <line x1={c} y1={c} x2={x} y2={y} stroke="var(--border)" stroke-width="0.8" />
    {/each}
    {#each series as s}
      <polygon points={poly(s.values)} fill={s.dashed ? 'none' : s.color} fill-opacity={s.dashed ? 0 : 0.22}
        stroke={s.color} stroke-width="2" stroke-dasharray={s.dashed ? '4 3' : ''} stroke-linejoin="round" />
    {/each}
    {#if series[0]}
      {#each axes as a, i}
        {@const [x, y] = pt(i, series[0].values?.[a.key] ?? 0)}
        <circle cx={x} cy={y} r="3" fill={series[0].color} />
      {/each}
    {/if}
    {#each axes as a, i}
      {@const [x, y] = pt(i, 118)}
      <text {x} y={y + 4} text-anchor={anchor(i)} font-size="12" fill="var(--text)" font-weight="600">{a.label}</text>
      {#if series[0]}
        <text {x} y={y + 18} text-anchor={anchor(i)} font-size="11" fill="var(--muted)">{Math.round(series[0].values?.[a.key] ?? 0)}</text>
      {/if}
    {/each}
  </svg>
  {#if series.length > 1}
    <div class="small" style="display:flex; gap:14px; justify-content:center; margin-top:4px">
      {#each series as s}
        <span><span style="display:inline-block; width:14px; height:3px; background:{s.color}; vertical-align:middle; margin-right:4px"></span>{s.label}</span>
      {/each}
    </div>
  {/if}
{/if}
