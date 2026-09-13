/**
 * Base-aware URL builders and URL view-state codecs shared by server components and client scripts.
 */
import type { Source, ViewMode } from './domain';

export const BASE = '/retrospective-eip-complexity/';

export function basePath(value = ''): string {
  return `${BASE}${value.replace(/^\/+/, '')}`;
}

export interface EipViewState {
  fork?: string | null;
  view?: ViewMode | null;
  rubric?: number | null;
}

function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

export function eipRoute(eip: number, state: EipViewState = {}, hash = ''): string {
  return basePath(`eips/${eip}/${query({ fork: state.fork, view: state.view, rubric: state.rubric })}${hash}`);
}

export function forkRoute(fork: string): string {
  return basePath(fork === 'hegota' ? 'prospective/hegota/' : `forks/${fork}/`);
}

export interface CompareState {
  eips: number[];
  fork?: string | null;
  source?: Source | 'compare' | null;
  rubric?: number | null;
}

export function compareRoute(state: CompareState): string {
  return basePath(`eips/compare/${query({ eips: state.eips.length ? state.eips.join(',') : null, fork: state.fork, source: state.source, rubric: state.rubric })}`);
}

export function parseCompareState(search: string): CompareState {
  const params = new URLSearchParams(search);
  const eips = (params.get('eips') ?? '')
    .split(',')
    .map((value) => Number.parseInt(value, 10))
    .filter((value) => Number.isFinite(value) && value > 0);
  const source = params.get('source');
  const rubric = Number.parseInt(params.get('rubric') ?? '', 10);
  return {
    eips: [...new Set(eips)],
    fork: params.get('fork'),
    source: source === 'llm' || source === 'human' || source === 'compare' ? source : null,
    rubric: Number.isFinite(rubric) ? rubric : null,
  };
}

export function parseEipViewState(search: string): EipViewState {
  const params = new URLSearchParams(search);
  const view = params.get('view');
  const rubric = Number.parseInt(params.get('rubric') ?? '', 10);
  return {
    fork: params.get('fork'),
    view: view === 'llm' || view === 'human' || view === 'compare' ? view : null,
    rubric: Number.isFinite(rubric) ? rubric : null,
  };
}

/** Replace the current URL's query string without adding a history entry. */
export function replaceQuery(params: Record<string, string | number | null | undefined>, hash = window.location.hash): void {
  const next = `${window.location.pathname}${query(params)}${hash}`;
  window.history.replaceState(window.history.state, '', next);
}
