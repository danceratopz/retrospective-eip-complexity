/**
 * One renderer for stacked criterion bars, shared by the server component and client scripts so the
 * markup, accessible name, and tooltip conventions are identical everywhere.
 */
import { DISPLAY_INDEX, criterionAbbreviation } from './criteria';

export interface BarSegment {
  id: string;
  score: number;
  detail?: string | null;
  /** Overrides for stacks that are not criterion stacks (for example scope timing). */
  color?: string;
  ink?: string;
  abbreviation?: string;
}

export interface StackedBarOptions {
  segments: BarSegment[];
  labels: Record<string, string> | Map<string, string>;
  total?: number;
  max?: number;
  normalized?: boolean;
  size?: 'compact' | 'regular' | 'large';
  label: string;
  unit?: string;
  showTotal?: boolean;
  className?: string;
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
}

export function stackedBarHtml(options: StackedBarOptions): string {
  const { segments, labels, total, max, normalized = false, size = 'regular', label, unit = 'points', showTotal = false, className } = options;
  const name = (id: string) => (labels instanceof Map ? labels.get(id) : labels[id]) ?? id;
  const ordered = segments
    .filter((segment) => segment.score > 0)
    .sort((a, b) => (DISPLAY_INDEX.get(a.id) ?? 99) - (DISPLAY_INDEX.get(b.id) ?? 99));
  const sum = total ?? ordered.reduce((value, segment) => value + segment.score, 0);
  const scale = normalized ? sum : Math.max(max ?? sum, sum);
  const widthPercent = scale > 0 ? (sum / scale) * 100 : 0;
  const percent = (value: number) => (sum > 0 ? `${Math.round((value / sum) * 100)}%` : '0%');
  const readout = ordered.map((segment) => `${name(segment.id)} ${segment.score}`).join(', ');
  const accessibleName = `${label}: ${sum} ${unit}${ordered.length ? `. ${readout}.` : '.'}`;
  const body = ordered.map((segment) => `${name(segment.id)}: ${segment.score} (${percent(segment.score)})`).join('\n');
  const fill = (segment: BarSegment) => (segment.color ? escapeHtml(segment.color) : `var(--criterion-${escapeHtml(segment.id)})`);
  const ink = (segment: BarSegment) => (segment.ink ? escapeHtml(segment.ink) : segment.color ? '#ffffff' : `var(--criterion-ink-${escapeHtml(segment.id)})`);
  const abbreviation = (segment: BarSegment) => escapeHtml(segment.abbreviation ?? criterionAbbreviation(segment.id));
  const segmentsHtml = ordered
    .map(
      (segment) =>
        `<span class="stack-segment" style="flex-grow:${segment.score};--fill:${fill(segment)};--ink:${ink(segment)}" data-tip data-tip-title="${escapeHtml(`${name(segment.id)} — ${segment.score}`)}" data-tip-body="${escapeHtml([`${percent(segment.score)} of ${sum} ${unit}`, segment.detail ?? ''].filter(Boolean).join('\n'))}" aria-hidden="true"><span class="stack-abbr">${abbreviation(segment)}</span></span>`,
    )
    .join('');
  const classes = ['stack', `stack-${size}`, className].filter(Boolean).join(' ');
  return (
    `<div class="${classes}" tabindex="0" role="img" aria-label="${escapeHtml(accessibleName)}" data-tip data-tip-title="${escapeHtml(`${label}: ${sum} ${unit}`)}" data-tip-body="${escapeHtml(body)}">` +
    `<div class="stack-track" style="width:${widthPercent}%">${segmentsHtml}</div>` +
    (showTotal ? `<span class="stack-total" aria-hidden="true">${sum}</span>` : '') +
    `</div>`
  );
}
