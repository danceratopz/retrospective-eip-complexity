/**
 * Light/dark theme support for client scripts. The theme itself lives in CSS tokens; the layout's
 * head script sets `data-theme` (explicit choice) and `data-theme-effective` (what is shown) on <html>
 * and dispatches `themechange` on document when it changes.
 */

export const THEME_EVENT = 'themechange';

export function isDark(): boolean {
  return document.documentElement.dataset.themeEffective === 'dark';
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Colours for client-built charts, read from the active CSS tokens. */
export function chartColors() {
  return {
    ink: token('--chart-ink'),
    muted: token('--chart-muted'),
    grid: token('--chart-grid'),
    point: token('--chart-point'),
    fit: token('--chart-fit'),
    band: token('--chart-band'),
    hegota: token('--chart-hegota'),
    surface: token('--surface'),
  };
}

/** Vega-Lite config for the active theme. */
export function chartConfig() {
  const c = chartColors();
  const axis = { labelColor: c.muted, titleColor: c.ink, gridColor: c.grid, domainColor: c.grid, tickColor: c.grid };
  return {
    background: null,
    axis,
    legend: { labelColor: c.muted, titleColor: c.ink },
    header: { labelColor: c.ink, titleColor: c.ink },
    title: { color: c.ink, subtitleColor: c.muted },
    text: { color: c.ink },
    view: { stroke: null },
  };
}

function luminance(hex: string): number | null {
  const match = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return null;
  const full = match[1].length === 3 ? [...match[1]].map((ch) => ch + ch).join('') : match[1];
  const [r, g, b] = [0, 2, 4].map((offset) => parseInt(full.slice(offset, offset + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const AXIS_COLOR_KEYS: Record<string, keyof ReturnType<typeof chartColors>> = {
  labelColor: 'muted',
  titleColor: 'ink',
  gridColor: 'grid',
  domainColor: 'grid',
  tickColor: 'grid',
};

/**
 * Adapt a published light-theme spec for dark mode: axis colours follow the theme, near-black text and
 * strokes become light ink, and near-white fills and outlines become the dark surface. Data colours that
 * encode categories are left unchanged.
 */
export function themedSpec<T>(spec: T): T {
  if (!isDark()) return spec;
  const c = chartColors();
  const visit = (value: any): any => {
    if (Array.isArray(value)) return value.map(visit);
    if (!value || typeof value !== 'object') return value;
    const out: Record<string, any> = {};
    for (const [key, item] of Object.entries(value)) {
      if (key === 'values' || key === 'data') { out[key] = item; continue; }
      if (typeof item === 'string' && AXIS_COLOR_KEYS[key]) { out[key] = c[AXIS_COLOR_KEYS[key]]; continue; }
      if (typeof item === 'string' && ['color', 'fill', 'stroke', 'labelColor', 'titleColor'].includes(key)) {
        const lum = item.toLowerCase() === 'white' ? 1 : luminance(item);
        if (lum !== null && lum < 0.22) { out[key] = c.ink; continue; }
        if (lum !== null && lum > 0.88) { out[key] = key === 'stroke' ? c.surface : c.grid; continue; }
      }
      out[key] = visit(item);
    }
    return out;
  };
  const themed = visit(spec);
  themed.config = { ...(themed.config ?? {}), ...chartConfig(), axis: { ...(themed.config?.axis ?? {}), ...chartConfig().axis } };
  return themed;
}
