export const pct = (p, d = 0) => `${(p * 100).toFixed(d)}%`;
export const fx = (x, d = 1) => (x == null ? '–' : Number(x).toFixed(d));
export const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

export const REGION_LABEL = { AMER: 'Americas', EMEA: 'EMEA', PAC: 'Pacific', CN: 'China' };
export const ROLE_LABEL = {
  duelist: '타격대', initiator: '척후대', controller: '전략가', sentinel: '감시자', flex: '기타',
};

// Diverging heat colour: blue (below lo..mid) -> neutral grey (mid) -> red (above).
export function heat(pp, lo = 80, hi = 130) {
  const t = Math.max(-1, Math.min(1, ((pp - lo) / (hi - lo)) * 2 - 1));
  const hue = t < 0 ? 215 : 355;
  return `hsl(${hue} ${Math.round(70 * Math.abs(t))}% ${26 + 12 * Math.abs(t)}%)`;
}

// All times shown in Korea Standard Time.
export function kst(iso) {
  if (!iso) return '–';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(d) + ' KST';
}

export function kstShort(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(d);
}
