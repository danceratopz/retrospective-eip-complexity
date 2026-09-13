/**
 * Client-side EIP comparison: reconstructs the view entirely from the URL and the compact compare index.
 */
import { DISPLAY_INDEX, criterionAbbreviation } from './criteria';
import type { Source, Status, Tier } from './domain';
import { SOURCE_LABELS, TIER_LABELS, statusLabel } from './labels';
import { compareRoute, eipRoute, parseCompareState, type CompareState } from './routes';
import { stackedBarHtml } from './stacked-bar';

export const MAX_EIPS = 4;

interface IndexAssessment {
  id: string;
  eip: number;
  fork: string;
  source: Source;
  rubric_revision: number;
  role: string;
  status: Status;
  scored: boolean;
  score: number | null;
  tier: Tier | null;
  scores: Array<number | null>;
  under_specified: boolean;
  affected_criteria: string[];
}

export interface CompareIndex {
  criteria: Array<{ id: string; label: string; short_definition: string; rubric_revisions: number[] }>;
  rubrics: Record<string, { criteria: string[]; tier_thresholds: unknown; nominal_maximum: number }>;
  forks: Array<{ fork: string; name: string; short_name: string }>;
  eips: Array<{ eip: number; title: string; forks: string[]; default_fork: string; snapshot_status: Record<string, string> }>;
  assessments: IndexAssessment[];
}

interface Column {
  eip: number;
  title: string;
  fork: string;
  forkName: string;
  llm: IndexAssessment | null;
  human: IndexAssessment | null;
  llmStatus: Status;
  humanStatus: Status;
}

export type SourceMode = 'llm' | 'human' | 'compare';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, attributes: Record<string, string> = {}, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

export function resolveColumns(index: CompareIndex, state: CompareState, mode: SourceMode): Column[] {
  const forkName = new Map(index.forks.map((item) => [item.fork, item.name]));
  const columns: Column[] = [];
  for (const eip of state.eips.slice(0, MAX_EIPS)) {
    const entry = index.eips.find((item) => item.eip === eip);
    if (!entry) continue;
    const fork = state.fork && entry.forks.includes(state.fork) ? state.fork : entry.default_fork;
    const candidates = index.assessments.filter((item) => item.eip === eip && item.fork === fork);
    const rubric = state.rubric ?? null;
    const pick = (source: Source): IndexAssessment | null => {
      const own = candidates.filter((item) => item.source === source);
      if (!own.length) return null;
      if (rubric) return own.find((item) => item.rubric_revision === rubric) ?? null;
      if (mode === 'compare') {
        // Prefer the revision under which both sources exist.
        const other = candidates.filter((item) => item.source !== source).map((item) => item.rubric_revision);
        const shared = own.filter((item) => other.includes(item.rubric_revision));
        if (shared.length) return shared.sort((a, b) => b.rubric_revision - a.rubric_revision)[0];
      }
      return own.sort((a, b) => (a.role === 'primary' ? -1 : 1) - (b.role === 'primary' ? -1 : 1) || b.rubric_revision - a.rubric_revision)[0];
    };
    const llm = pick('llm');
    const human = pick('human');
    const notApplicable = candidates.length === 0 && entry.forks.includes(fork);
    columns.push({
      eip,
      title: entry.title,
      fork,
      forkName: forkName.get(fork) ?? fork,
      llm,
      human,
      llmStatus: llm ? llm.status : notApplicable ? 'not_applicable' : 'not_available',
      humanStatus: human ? human.status : 'not_available',
    });
  }
  return columns;
}

function statusBadge(status: Status, mode: 'retrospective' | 'prospective'): HTMLElement {
  const glyphs: Record<Status, string> = { complete: '●', available_in_open_pr: '◐', in_progress: '◔', incomplete: '◌', not_applicable: '⊘', not_available: '○' };
  const badge = el('span', { class: `status status-${status} status-small` });
  badge.append(el('span', { class: 'status-glyph', 'aria-hidden': 'true' }, glyphs[status]), el('span', {}, statusLabel(status, mode)));
  return badge;
}

function scoreOf(assessment: IndexAssessment | null, criterionIndex: number): number | null {
  if (!assessment || !assessment.scored) return null;
  return assessment.scores[criterionIndex];
}

export function render(root: HTMLElement, index: CompareIndex, state: CompareState): void {
  const mode: SourceMode = state.source ?? 'llm';
  const columns = resolveColumns(index, state, mode);
  const labels = new Map(index.criteria.map((item) => [item.id, item.label]));
  const output = root.querySelector<HTMLElement>('[data-compare-output]')!;
  output.replaceChildren();
  const empty = root.querySelector<HTMLElement>('[data-compare-empty]');
  if (empty) empty.hidden = columns.length > 0;
  if (!columns.length) return;

  const prospective = (column: Column) => (column.fork === 'hegota' ? 'prospective' : 'retrospective');
  const sources: Source[] = mode === 'compare' ? ['llm', 'human'] : [mode];
  const assessmentFor = (column: Column, source: Source) => (source === 'llm' ? column.llm : column.human);
  const scale = Math.max(1, ...columns.flatMap((column) => sources.map((source) => assessmentFor(column, source)?.score ?? 0)));

  // Bars ------------------------------------------------------------------------------------------
  const bars = el('div', { class: 'compare-grid' });
  for (const column of columns) {
    const card = el('article', { class: 'compare-card' });
    const heading = el('h3');
    const link = el('a', { href: eipRoute(column.eip, { fork: column.fork }) }, `EIP-${column.eip}`);
    heading.append(link, el('span', { class: 'compare-card-title' }, ` ${column.title}`));
    card.append(heading, el('p', { class: 'muted compare-card-context' }, column.forkName));
    for (const source of sources) {
      const assessment = assessmentFor(column, source);
      const row = el('div', { class: 'compare-bar-row' });
      const label = el('span', { class: 'compare-bar-label' }, SOURCE_LABELS[source]);
      row.append(label);
      if (assessment && assessment.scored) {
        const segments = index.criteria
          .map((criterion, position) => ({ id: criterion.id, score: assessment.scores[position] ?? 0 }))
          .filter((segment) => segment.score > 0);
        const holder = el('div', { class: 'compare-bar-holder' });
        holder.innerHTML = stackedBarHtml({ segments, labels, total: assessment.score ?? 0, max: scale, size: 'regular', showTotal: true, label: `EIP-${column.eip} ${SOURCE_LABELS[source]} complexity` });
        row.append(holder);
        const meta = el('span', { class: 'muted compare-bar-meta' }, `${TIER_LABELS[assessment.tier!]} · checklist revision ${assessment.rubric_revision}${assessment.under_specified ? ' · under-specified' : ''}`);
        row.append(meta);
      } else {
        row.append(statusBadge(source === 'llm' ? column.llmStatus : column.humanStatus, prospective(column)));
      }
      card.append(row);
    }
    if (mode === 'compare' && column.llm?.scored && column.human?.scored) {
      const delta = column.llm.score! - column.human.score!;
      card.append(el('p', { class: 'compare-card-delta' }, `Δ total (LLM − Human): ${delta > 0 ? '+' : ''}${delta}`));
    }
    bars.append(card);
  }
  output.append(el('h2', {}, 'Complexity profiles'), el('p', { class: 'muted' }, 'Bars share one scale so lengths are comparable. Hover or focus a bar for every criterion.'), bars);

  // Matrix ------------------------------------------------------------------------------------------
  const present = index.criteria
    .map((criterion, position) => {
      const values = columns.flatMap((column) => sources.map((source) => scoreOf(assessmentFor(column, source), position))).filter((value): value is number => value !== null);
      const maxValue = values.length ? Math.max(...values) : 0;
      const spread = values.length ? maxValue - Math.min(...values) : 0;
      return { criterion, position, maxValue, spread, present: values.some((value) => value > 0) };
    })
    .filter((row) => row.present);
  const orderBy = (root.querySelector<HTMLSelectElement>('[data-compare-order]')?.value ?? 'score') as 'score' | 'spread' | 'stable';
  present.sort((a, b) => {
    const stable = (DISPLAY_INDEX.get(a.criterion.id) ?? 99) - (DISPLAY_INDEX.get(b.criterion.id) ?? 99);
    if (orderBy === 'spread') return b.spread - a.spread || b.maxValue - a.maxValue || stable;
    if (orderBy === 'stable') return stable;
    return b.maxValue - a.maxValue || b.spread - a.spread || stable;
  });

  const region = el('div', { class: 'table-region', role: 'region', tabindex: '0', 'aria-label': 'Criterion comparison matrix' });
  const table = el('table', { class: 'matrix' });
  table.append(el('caption', {}, `Criterion scores for ${columns.length} EIP${columns.length === 1 ? '' : 's'} (${mode === 'compare' ? 'LLM / Human, Δ = LLM − Human' : SOURCE_LABELS[mode]} assessment). Only criteria with a non-zero score in at least one column are listed.`));
  const head = el('thead');
  const headRow = el('tr');
  headRow.append(el('th', { scope: 'col' }, 'Criterion'));
  for (const column of columns) {
    const cell = el('th', { scope: 'col', class: 'number' });
    cell.append(el('a', { href: eipRoute(column.eip, { fork: column.fork }) }, `EIP-${column.eip}`), el('span', { class: 'matrix-fork' }, column.forkName));
    headRow.append(cell);
  }
  head.append(headRow);
  const body = el('tbody');
  for (const row of present) {
    const tr = el('tr');
    const th = el('th', { scope: 'row' });
    th.append(el('span', { class: 'swatch', style: `--fill:var(--criterion-${row.criterion.id});--ink:var(--criterion-ink-${row.criterion.id})`, 'aria-hidden': 'true' }, criterionAbbreviation(row.criterion.id)), el('span', { class: 'criterion-name' }, row.criterion.label));
    tr.append(th);
    for (const column of columns) {
      const td = el('td', { class: 'number' });
      if (mode === 'compare') {
        const llm = scoreOf(column.llm, row.position);
        const human = scoreOf(column.human, row.position);
        if (llm === null && human === null) td.append(el('span', { class: 'muted' }, '—'));
        else {
          td.append(el('span', { class: 'matrix-pair' }, `${llm ?? '—'} / ${human ?? '—'}`));
          if (llm !== null && human !== null) {
            const delta = llm - human;
            td.append(el('span', { class: `matrix-delta ${delta > 0 ? 'delta-pos' : delta < 0 ? 'delta-neg' : ''}` }, delta === 0 ? '0' : delta > 0 ? `+${delta}` : `−${Math.abs(delta)}`));
          }
        }
      } else {
        const value = scoreOf(assessmentFor(column, mode), row.position);
        if (value === null) td.append(el('span', { class: 'muted', title: statusLabel(mode === 'llm' ? column.llmStatus : column.humanStatus, prospective(column)) }, '—'));
        else {
          td.textContent = String(value);
          if (value === row.maxValue && row.spread > 0) td.classList.add('matrix-max');
        }
      }
      tr.append(td);
    }
    body.append(tr);
  }
  const foot = el('tfoot');
  const totalRow = el('tr');
  totalRow.append(el('th', { scope: 'row' }, 'Total'));
  for (const column of columns) {
    const td = el('td', { class: 'number' });
    if (mode === 'compare') {
      const llm = column.llm?.scored ? column.llm.score : null;
      const human = column.human?.scored ? column.human.score : null;
      td.textContent = `${llm ?? '—'} / ${human ?? '—'}`;
    } else {
      const assessment = assessmentFor(column, mode);
      td.textContent = assessment?.scored ? String(assessment.score) : '—';
    }
    totalRow.append(td);
  }
  foot.append(totalRow);
  table.append(head, body, foot);
  region.append(table);
  output.append(el('h2', {}, 'Criterion matrix'), region);
  if (!present.length) output.append(el('p', { class: 'muted' }, 'No criterion scores are available for this selection.'));
}

export function readState(): CompareState {
  return parseCompareState(window.location.search);
}

export function writeState(state: CompareState): void {
  window.history.replaceState(window.history.state, '', compareRoute(state));
}

export function optionLabel(entry: CompareIndex['eips'][number]): string {
  return `EIP-${entry.eip} — ${entry.title}`;
}
