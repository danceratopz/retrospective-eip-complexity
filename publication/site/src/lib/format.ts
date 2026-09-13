/** Small formatting helpers shared by components. */

export function isoDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : '—';
}

export function shortCommit(value: string | null | undefined, length = 10): string {
  return value ? value.slice(0, length) : '—';
}

export function signed(value: number): string {
  if (value > 0) return `+${value}`;
  if (value < 0) return `−${Math.abs(value)}`;
  return '0';
}

/** DOM-safe identifier derived from an assessment or comparison id such as "prague:7251:llm:r2". */
export function domId(value: string): string {
  return value.replace(/[^A-Za-z0-9_-]+/g, '-');
}

export function truncate(value: string | null | undefined, length = 160): string {
  if (!value) return '';
  return value.length > length ? `${value.slice(0, length - 1).trimEnd()}…` : value;
}

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}
