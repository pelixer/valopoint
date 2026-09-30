import { createEngine } from './engine.js';

export const app = $state({ model: null, engine: null, error: null, route: parse() });

function parse() {
  const h = location.hash.replace(/^#\/?/, '');
  const [page, ...rest] = h.split('/');
  return { page: page || 'teams', arg: rest.map(decodeURIComponent).join('/') || null };
}

window.addEventListener('hashchange', () => {
  app.route = parse();
  window.scrollTo(0, 0);
});

export async function loadModel() {
  try {
    const res = await fetch(`./data/model.json?t=${Date.now()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const model = await res.json();
    app.model = model;
    app.engine = createEngine(model);
  } catch (e) {
    app.error = String(e);
  }
}

// small persisted per-device settings (locked bracket results etc.)
export function persisted(key, init) {
  let v = init;
  try { const s = localStorage.getItem(key); if (s) v = JSON.parse(s); } catch {}
  return {
    get: () => v,
    set: (nv) => { v = nv; try { localStorage.setItem(key, JSON.stringify(nv)); } catch {} },
  };
}
