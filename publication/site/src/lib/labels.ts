/**
 * Single source of reader-facing terminology. Components never spell these strings themselves.
 */
import type { Confidence, Mode, Source, Status, Tier, ViewMode } from './domain';

export const SITE_TITLE = 'Retrospective LLM-Based Complexity Evaluations';

export const EVALUATOR_LABELS: Record<Source, string> = { llm: 'LLM', human: 'Human' };
export const EVALUATOR_DESCRIPTIONS: Record<Source, string> = {
  llm: 'Automated assessment by an LLM working from a sealed EIP revision and the pinned rubric.',
  human: 'Checklist published by STEEL team reviewers in the ethspecs/pm repository.',
};

export const VIEW_LABELS: Record<ViewMode, string> = { llm: 'LLM', human: 'Human', compare: 'Compare' };

export const TIER_LABELS: Record<Tier, string> = { low: 'Low', medium: 'Medium', high: 'High' };
export const TIER_MEANINGS: Record<Tier, string> = {
  low: 'Minor feature or localized change; existing tests largely unaffected.',
  medium: 'Moderate change affecting multiple components; moderate cross-EIP testing.',
  high: 'Broad or deep impact on protocol behavior; high regression risk or intensive cross-EIP testing.',
};

export const CONFIDENCE_LABELS: Record<Confidence, string> = { low: 'Low', medium: 'Medium', high: 'High' };
export const CONFIDENCE_NOT_RECORDED = 'Not recorded';

export const STATUS_LABELS: Record<Status, string> = {
  complete: 'Complete',
  available_in_open_pr: 'Available in open PR',
  in_progress: 'Draft PR',
  incomplete: 'Incomplete',
  not_applicable: 'Not applicable to EL rubric',
  not_available: 'Not available',
};
export const STATUS_DESCRIPTIONS: Record<Status, string> = {
  complete: 'A complete assessment is published and merged.',
  available_in_open_pr: 'A complete checklist exists only in an open, non-draft pull request.',
  in_progress: 'The checklist is in an open draft pull request; if its cells and total parse, it is scored like any other assessment.',
  incomplete: 'A checklist exists but has unresolved cells, missing rows, or inconsistent totals; it carries no score.',
  not_applicable: 'Consensus-layer-only or explicitly excluded work; the execution-layer rubric assigns no score, and this is never a zero.',
  not_available: 'No assessment from this evaluator exists; for Hegotá this means the human checklist is still pending.',
};

/** A prospective checklist that does not exist yet is pending; retrospective data is simply absent. */
export function statusLabel(status: Status, mode: Mode = 'retrospective'): string {
  if (status === 'not_available' && mode === 'prospective') return 'Pending';
  return STATUS_LABELS[status];
}

export const EVALUATOR_LABEL = 'Evaluator';
export const EVALUATOR_FILTER_LABELS = { both: 'Both evaluators', llm: 'LLM only', human: 'Human only' } as const;

export const UNDER_SPECIFIED_LABEL = 'Under-specified at assessment cutoff';
export const UNDER_SPECIFIED_SHORT = 'Under-specified';
export const UNDER_SPECIFIED_DEFINITION =
  'The EIP text available at the assessment cutoff left material behavior unresolved. The affected criteria and the plausible total range record that uncertainty.';

export const SCOPE_TIMING_LABELS = {
  included_at_cutoff: 'Included by cutoff',
  added_after_cutoff: 'Added after cutoff',
} as const;

export const SNAPSHOT_STATUS_LABELS = { PFI: 'Proposed for inclusion', SFI: 'Scheduled for inclusion', CFI: 'Considered for inclusion' } as const;

export const MODE_LABELS: Record<Mode, string> = { retrospective: 'Retrospective', prospective: 'Prospective' };

export const ROLE_LABELS = {
  primary: 'Primary study assessment',
  historical_rubric_rerun: 'Same-rubric re-run for the human comparison',
  published_checklist: 'Published checklist',
} as const;

export const AGREEMENT_LABELS = { exact: 'Agree', minor: 'Differ by 1', major: 'Differ by 2+' } as const;

export function rubricLabel(revision: number): string {
  return `Checklist revision ${revision}`;
}

export function forkContextLabel(mode: Mode): string {
  return mode === 'prospective' ? 'Snapshot' : 'Assessment cutoff';
}
