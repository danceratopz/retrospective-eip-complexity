/**
 * Client-side comparison of assessments: reconstructs the view entirely from the URL and the compact
 * compare index. Any mix of evaluators, EIPs, and fork contexts can be compared; the page flags mixed
 * checklist revisions and links same-EIP pairs to the detailed Human-versus-LLM view.
 */
import { DISPLAY_INDEX, criterionAbbreviation } from './criteria';
import type { Source, Status, Tier } from './domain';
import { EVALUATOR_LABELS, TIER_LABELS, rubricLabel, statusLabel } from './labels';
import { COMPARE_LIMIT, compareRoute, eipRoute, parseCompareState, type CompareState } from './routes';
import { stackedBarHtml } from './stacked-bar';

export interface IndexAssessment {
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

function el<K extends keyof HTMLElementTagNameMap>(tag: K, attributes: Record<string, string> = {}, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

/** Translate a legacy `?eips=&fork=&source=` selection into assessment ids. */
export function resolveLegacy(index: CompareIndex, state: CompareState): string[] {
  if (state.assessments.length || !state.eips?.length) return state.assessments;
  const ids: string[] = [];
  for (const eip of state.eips) {
    const entry = index.eips.find((item) => item.eip === eip);
    if (!entry) continue;
    const fork = state.fork && entry.forks.includes(state.fork) ? state.fork : entry.default_fork;
    const candidates = index.assessments.filter((item) => item.eip === eip && item.fork === fork && item.scored);
    const llm = candidates.filter((item) => item.source === 'llm');
    const human = candidates.filter((item) => item.source === 'human');
    const primary = llm.find((item) => item.role === 'primary') ?? llm[0];
    if (state.source === 'human') {
      if (human[0]) ids.push(human[0].id);
    } else if (state.source === 'compare' && human[0]) {
      const sameRevision = llm.find((item) => item.rubric_revision === human[0].rubric_revision) ?? primary;
      if (sameRevision) ids.push(sameRevision.id);
      ids.push(human[0].id);
    } else if (primary) {
      ids.push(primary.id);
    }
  }
  return ids;
}

export function assessmentLabel(index: CompareIndex, assessment: IndexAssessment): string {
  const entry = index.eips.find((item) => item.eip === assessment.eip);
  const fork = index.forks.find((item) => item.fork === assessment.fork);
  return `EIP-${assessment.eip} · ${EVALUATOR_LABELS[assessment.source]} r${assessment.rubric_revision} · ${fork?.short_name ?? assessment.fork} — ${entry?.title ?? ''}`;
}

function statusBadge(status: Status, mode: 'retrospective' | 'prospective'): HTMLElement {
  const glyphs: Record<Status, string> = { complete: '●', available_in_open_pr: '◐', in_progress: '◔', incomplete: '◌', not_applicable: '⊘', not_available: '○' };
  const badge = el('span', { class: `status status-${status} status-small` });
  badge.append(el('span', { class: 'status-glyph', 'aria-hidden': 'true' }, glyphs[status]), el('span', {}, statusLabel(status, mode)));
  return badge;
}

function sourceBadge(assessment: IndexAssessment): HTMLElement {
  const badge = el('span', { class: `evaluator evaluator-${assessment.source} evaluator-small` });
  badge.append(el('span', { class: 'evaluator-glyph', 'aria-hidden': 'true' }, assessment.source === 'human' ? '⚇' : '⌬'), el('span', {}, EVALUATOR_LABELS[assessment.source]), el('span', { class: 'evaluator-revision' }, rubricLabel(assessment.rubric_revision)));
  return badge;
}

const signed = (value: number) => (value > 0 ? `+${value}` : value < 0 ? `−${Math.abs(value)}` : '0');

export function render(root: HTMLElement, index: CompareIndex, state: CompareState, onSwap: (from: string, to: string) => void): void {
  const byId = new Map(index.assessments.map((item) => [item.id, item]));
  const columns = state.assessments.map((id) => byId.get(id)).filter((item): item is IndexAssessment => Boolean(item)).slice(0, COMPARE_LIMIT);
  const labels = new Map(index.criteria.map((item) => [item.id, item.label]));
  const forkName = new Map(index.forks.map((item) => [item.fork, item.name]));
  const titles = new Map(index.eips.map((item) => [item.eip, item.title]));
  const output = root.querySelector<HTMLElement>('[data-compare-output]')!;
  output.replaceChildren();
  const empty = root.querySelector<HTMLElement>('[data-compare-empty]');
  if (empty) empty.hidden = columns.length > 0;
  if (!columns.length) return;

  const mode = (column: IndexAssessment) => (column.fork === 'hegota' ? 'prospective' : 'retrospective');
  const scale = Math.max(1, ...columns.map((column) => column.score ?? 0));
  const revisions = new Set(columns.map((column) => column.rubric_revision));

  // Notices ----------------------------------------------------------------------------------------
  if (revisions.size > 1) {
    const notice = el('div', { class: 'caveat' });
    notice.append(el('strong', {}, 'Mixed checklist revisions. '), document.createTextNode('Revision 1 has 24 criteria with tiers <10 / 10–19 / ≥20; revision 2 has 28 criteria with tiers <12 / 12–22 / ≥23. Totals are not like-for-like, and criteria that exist in only one revision are marked in the matrix.'));
    for (const column of columns) {
      const counterpart = index.assessments.find((item) => item.eip === column.eip && item.fork === column.fork && item.source === column.source && item.scored && item.rubric_revision !== column.rubric_revision && !columns.includes(item));
      if (!counterpart) continue;
      const button = el('button', { type: 'button', class: 'button-secondary swap-button' }, `Use the ${EVALUATOR_LABELS[column.source]} ${rubricLabel(counterpart.rubric_revision).toLowerCase()} assessment of EIP-${column.eip} instead`);
      button.addEventListener('click', () => onSwap(column.id, counterpart.id));
      const holder = el('div');
      holder.append(button);
      notice.append(holder);
    }
    output.append(notice);
  }
  const pairs = new Map<string, IndexAssessment[]>();
  for (const column of columns) pairs.set(`${column.fork}:${column.eip}`, [...(pairs.get(`${column.fork}:${column.eip}`) ?? []), column]);
  for (const [, group] of pairs) {
    if (group.some((item) => item.source === 'llm') && group.some((item) => item.source === 'human')) {
      const first = group[0];
      const paragraph = el('p', { class: 'source-note' });
      paragraph.append(el('strong', {}, `Human and LLM assessments of EIP-${first.eip} are both selected. `), el('a', { href: eipRoute(first.eip, { fork: first.fork, view: 'compare' }) }, 'Open the detailed per-criterion comparison with rationale from both evaluators'), document.createTextNode('.'));
      output.append(paragraph);
    }
  }

  // Cards -------------------------------------------------------------------------------------------
  const cards = el('div', { class: 'compare-grid' });
  for (const column of columns) {
    const card = el('article', { class: 'compare-card' });
    const heading = el('h3');
    heading.append(el('a', { href: eipRoute(column.eip, { fork: column.fork, view: column.source }) }, `EIP-${column.eip}`), el('span', { class: 'compare-card-title' }, ` ${titles.get(column.eip) ?? ''}`));
    const meta = el('p', { class: 'muted compare-card-context' });
    meta.append(sourceBadge(column), document.createTextNode(` · ${forkName.get(column.fork) ?? column.fork}`));
    card.append(heading, meta);
    if (column.scored) {
      const segments = index.criteria.map((criterion, position) => ({ id: criterion.id, score: column.scores[position] ?? 0 })).filter((segment) => segment.score > 0);
      const holder = el('div', { class: 'compare-bar-holder' });
      holder.innerHTML = stackedBarHtml({ segments, labels, total: column.score ?? 0, max: scale, size: 'large', showTotal: true, label: `EIP-${column.eip} ${EVALUATOR_LABELS[column.source]} complexity` });
      card.append(holder, el('p', { class: 'muted compare-bar-meta' }, `${TIER_LABELS[column.tier!]}${column.under_specified ? ' · under-specified at cutoff' : ''}`));
    } else {
      card.append(statusBadge(column.status, mode(column)));
    }
    cards.append(card);
  }
  output.append(el('h2', {}, 'Complexity profiles'), el('p', { class: 'muted' }, 'Bars share one scale so lengths are comparable. Hover or focus a bar for every criterion.'), cards);

  // Matrix ------------------------------------------------------------------------------------------
  const present = index.criteria
    .map((criterion, position) => {
      const values = columns.map((column) => (column.scored ? column.scores[position] : null)).filter((value): value is number => value !== null);
      const maxValue = values.length ? Math.max(...values) : 0;
      const spread = values.length ? maxValue - Math.min(...values) : 0;
      return { criterion, position, maxValue, spread, present: values.some((value) => value > 0) };
    })
    .filter((row) => row.present);
  const orderBy = state.order ?? 'score';
  present.sort((a, b) => {
    const stable = (DISPLAY_INDEX.get(a.criterion.id) ?? 99) - (DISPLAY_INDEX.get(b.criterion.id) ?? 99);
    if (orderBy === 'spread') return b.spread - a.spread || b.maxValue - a.maxValue || stable;
    if (orderBy === 'stable') return stable;
    return b.maxValue - a.maxValue || b.spread - a.spread || stable;
  });
  const pairDelta = columns.length === 2 && columns.every((column) => column.scored);

  const region = el('div', { class: 'table-region', role: 'region', tabindex: '0', 'aria-label': 'Criterion comparison matrix' });
  const table = el('table', { class: 'matrix' });
  table.append(el('caption', {}, `Criterion scores for ${columns.length} assessment${columns.length === 1 ? '' : 's'}. Only criteria with a non-zero score in at least one column are listed${pairDelta ? '; Δ is the second column minus the first' : ''}.`));
  const head = el('thead');
  const headRow = el('tr');
  headRow.append(el('th', { scope: 'col' }, 'Criterion'));
  for (const column of columns) {
    const cell = el('th', { scope: 'col', class: 'number' });
    cell.append(el('a', { href: eipRoute(column.eip, { fork: column.fork, view: column.source }) }, `EIP-${column.eip}`), el('span', { class: 'matrix-fork' }, `${EVALUATOR_LABELS[column.source]} r${column.rubric_revision} · ${forkName.get(column.fork) ?? column.fork}`));
    headRow.append(cell);
  }
  if (pairDelta) headRow.append(el('th', { scope: 'col', class: 'number' }, 'Δ'));
  head.append(headRow);
  const body = el('tbody');
  for (const row of present) {
    const tr = el('tr');
    const th = el('th', { scope: 'row' });
    th.append(el('span', { class: 'swatch', style: `--fill:var(--criterion-${row.criterion.id});--ink:var(--criterion-ink-${row.criterion.id})`, 'aria-hidden': 'true' }, criterionAbbreviation(row.criterion.id)), el('span', { class: 'criterion-name' }, row.criterion.label));
    if (revisions.size > 1 && row.criterion.rubric_revisions.length === 1) th.append(el('span', { class: 'flag flag-revision', title: `Only in ${rubricLabel(row.criterion.rubric_revisions[0]).toLowerCase()}` }, `r${row.criterion.rubric_revisions[0]} only`));
    tr.append(th);
    const values: Array<number | null> = [];
    for (const column of columns) {
      const td = el('td', { class: 'number' });
      const inRevision = row.criterion.rubric_revisions.includes(column.rubric_revision);
      const value = column.scored && inRevision ? column.scores[row.position] : null;
      values.push(value);
      if (value === null) td.append(el('span', { class: 'muted', title: inRevision ? statusLabel(column.status, mode(column)) : `Not part of ${rubricLabel(column.rubric_revision).toLowerCase()}` }, inRevision ? '—' : 'n/a'));
      else {
        td.textContent = String(value);
        if (value === row.maxValue && row.spread > 0) td.classList.add('matrix-max');
      }
      tr.append(td);
    }
    if (pairDelta) {
      const [first, second] = values;
      const td = el('td', { class: 'number delta' });
      if (first === null || second === null) td.append(el('span', { class: 'muted' }, '—'));
      else {
        const delta = second - first;
        td.textContent = signed(delta);
        if (delta > 0) td.classList.add('delta-pos');
        if (delta < 0) td.classList.add('delta-neg');
      }
      tr.append(td);
    }
    body.append(tr);
  }
  const foot = el('tfoot');
  const totalRow = el('tr');
  totalRow.append(el('th', { scope: 'row' }, 'Total'));
  for (const column of columns) totalRow.append(el('td', { class: 'number' }, column.scored ? String(column.score) : '—'));
  if (pairDelta) totalRow.append(el('td', { class: 'number delta' }, signed((columns[1].score ?? 0) - (columns[0].score ?? 0))));
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
