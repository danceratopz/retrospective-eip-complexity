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

export type CompareOrder = 'score' | 'spread' | 'stable';

export interface CompareState {
  /** Assessment ids such as "amsterdam:7928:human:r1"; the canonical selection. */
  assessments: string[];
  /** Criterion ordering of the matrix; "score" is the default and is omitted from the URL. */
  order?: CompareOrder | null;
  /** Legacy selection by EIP number, resolved client-side against the compare index. */
  eips?: number[];
  fork?: string | null;
  source?: Source | 'compare' | null;
}

export const COMPARE_LIMIT = 6;

export function compareRoute(state: CompareState): string {
  const order = state.order && state.order !== 'score' ? state.order : null;
  if (state.assessments.length) return basePath(`eips/compare/${query({ a: state.assessments.join(','), order })}`);
  return basePath(`eips/compare/${query({ eips: state.eips?.length ? state.eips.join(',') : null, fork: state.fork, source: state.source, order })}`);
}

export function parseCompareState(search: string): CompareState {
  const params = new URLSearchParams(search);
  const assessments = (params.get('a') ?? '')
    .split(',')
    .map((value) => value.trim())
    .filter((value) => /^[a-z]+:\d+:(llm|human):r\d$/.test(value));
  const eips = (params.get('eips') ?? '')
    .split(',')
    .map((value) => Number.parseInt(value, 10))
    .filter((value) => Number.isFinite(value) && value > 0);
  const source = params.get('source');
  const order = params.get('order');
  return {
    assessments: [...new Set(assessments)],
    order: order === 'spread' || order === 'stable' ? order : null,
    eips: [...new Set(eips)],
    fork: params.get('fork'),
    source: source === 'llm' || source === 'human' || source === 'compare' ? source : null,
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
