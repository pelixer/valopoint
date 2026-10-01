import { createEngine } from './engine.js';

export const app = $state({ model: null, engine: null, brackets: [], bracketsAt: null, error: null, route: parse() });

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
    app.brackets = model.brackets ?? [];
    // live bracket (refreshed twice a day, independently of the model)
    try {
      const b = await fetch(`./data/brackets.json?t=${Date.now()}`);
      if (b.ok) {
        const bj = await b.json();
        if (bj.brackets?.length) { app.brackets = bj.brackets; app.bracketsAt = bj.generated_at; }
      }
    } catch {}
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
