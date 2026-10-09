/**
 * Numbers for the Hegotá scope deck, derived from the publication payload in one place.
 *
 * Previous forks come from the primary evaluation behind `fork_shipping` (Opus 5.5 · template v3). Hegotá
 * comes from `hegota_builder`, the same evaluation applied to the current SFI/CFI/PFI lists.
 */
import type { Publication } from '../domain';

/** Set `stamp` again if the deck ever shows numbers that are not the published primary evaluation. */
export const SCORES: { stamp?: string } = {};

const TEMPLATE_PATH = 'Templates/EIP-Complexity-Assessment.md';
export const TEMPLATE_V1_URL = `https://github.com/ethspecs/pm/blob/d936bcb34963cb5eec015dada2e4188e49fc14d5/${TEMPLATE_PATH}`;
export const TEMPLATE_V2_URL = `https://github.com/ethspecs/pm/blob/3d8c0128c5543dd3146341ef395aa344e4abea30/${TEMPLATE_PATH}`;
export const TEMPLATE_V2_PR_URL = 'https://github.com/ethspecs/pm/pull/101';
/** Same commit as the payload's checklist revision 3 source. */
export const TEMPLATE_V3_URL = `https://github.com/ethspecs/pm/blob/fe2f793b031adbb17826cfebd5bd2b502d1885c1/${TEMPLATE_PATH}`;
export const TEMPLATE_V3_PR_URL = 'https://github.com/ethspecs/pm/pull/147';

export interface ForkRow {
  fork: string;
  name: string;
  total: number;
  eipCount: number;
  heaviestEip: string;
  heaviestScore: number;
  days: number;
  devnet: string;
  mainnet: string;
  projected: boolean;
}

export function forkRows(data: Publication): ForkRow[] {
  return data.fork_shipping.rows.map((row: any) => ({
    fork: row.fork,
    name: row.fork_short,
    total: row.total_score,
    eipCount: row.at_cutoff_eips,
    heaviestEip: row.hardest_eip,
    heaviestScore: row.max_score,
    days: row.shipping_days,
    devnet: row.first_multi_el_devnet,
    mainnet: row.mainnet_at,
    projected: row.projected,
  }));
}

export interface LinearFit {
  slope: number;
  intercept: number;
  r: number;
  n: number;
  /** Half-width of the 95% confidence band for the mean at x. */
  halfWidth: (x: number) => number;
  predict: (x: number) => number;
}

/** Two-sided 97.5% Student t quantiles for small residual degrees of freedom. */
const T_975: Record<number, number> = { 1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306 };

/** Ordinary least squares with a 95% confidence band for the fitted mean. */
export function linearFit(points: Array<{ x: number; y: number }>): LinearFit {
  const n = points.length;
  const meanX = points.reduce((sum, point) => sum + point.x, 0) / n;
  const meanY = points.reduce((sum, point) => sum + point.y, 0) / n;
  const sxx = points.reduce((sum, point) => sum + (point.x - meanX) ** 2, 0);
  const syy = points.reduce((sum, point) => sum + (point.y - meanY) ** 2, 0);
  const sxy = points.reduce((sum, point) => sum + (point.x - meanX) * (point.y - meanY), 0);
  const slope = sxy / sxx;
  const intercept = meanY - slope * meanX;
  const residual = points.reduce((sum, point) => sum + (point.y - (intercept + slope * point.x)) ** 2, 0);
  const se = Math.sqrt(residual / (n - 2));
  const t = T_975[n - 2] ?? 1.96;
  return {
    slope,
    intercept,
    r: sxy / Math.sqrt(sxx * syy),
    n,
    predict: (x) => intercept + slope * x,
    halfWidth: (x) => t * se * Math.sqrt(1 / n + (x - meanX) ** 2 / sxx),
  };
}

export type ListKey = 'SFI' | 'CFI' | 'PFI';
export const LIST_ORDER: ListKey[] = ['SFI', 'CFI', 'PFI'];

export interface ListSummary {
  key: ListKey;
  entries: number;
  scored: number;
  total: number;
  members: BuilderEntry[];
}

interface BuilderEntry {
  eip: number;
  title: string;
  list: ListKey;
  status: 'scored' | 'not_applicable' | string;
  score: number | null;
}

export interface HegotaSnapshot {
  id: string;
  eipsCommit: string;
  cutoff: string;
  /** The EIP-8081 list state applied to the scores; differs from eipsCommit after a recorded list update. */
  listsLabel: string | null;
  listsCommit: string;
  listsAt: string;
}

export function hegotaSnapshot(data: Publication): HegotaSnapshot {
  const builder = data.hegota_builder;
  const lists = builder.lists_as_of ?? { label: null, commit: builder.eips_commit, committed_at: builder.information_cutoff_at };
  return { id: builder.snapshot_id, eipsCommit: builder.eips_commit, cutoff: builder.information_cutoff_at, listsLabel: lists.label, listsCommit: lists.commit, listsAt: lists.committed_at };
}

export function hegotaLists(data: Publication): ListSummary[] {
  const entries = data.hegota_builder.entries as BuilderEntry[];
  return LIST_ORDER.map((key) => {
    const members = entries.filter((entry) => entry.list === key);
    const scored = members.filter((entry) => entry.status === 'scored');
    return { key, entries: members.length, scored: scored.length, total: scored.reduce((sum, entry) => sum + (entry.score ?? 0), 0), members: scored };
  });
}
