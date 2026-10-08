/**
 * Single source of reader-facing terminology. Components never spell these strings themselves.
 */
import type { Confidence, Mode, Source, Status, Tier, ViewMode } from './domain';

export const SITE_TITLE = 'Retrospective LLM-Based Complexity Evaluations';

export const EVALUATOR_LABELS: Record<Source, string> = { llm: 'LLM', human: 'Human' };
export const EVALUATOR_DESCRIPTIONS: Record<Source, string> = {
  llm: 'Automated assessment by Claude Opus 5.5 of a sealed EIP revision against checklist revision 3, with the documents supplied in the prompt and no tools.',
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
export function statusLabel(status: Status, mode: Mode = 'retrospective', compact = false): string {
  if (compact && status === 'available_in_open_pr') return 'Open PR';
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
  previous_evaluation: 'Previous primary evaluation',
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

export const MODEL_LABELS: Record<string, string> = { 'claude-opus-5-5': 'Opus 5.5', 'gpt-5.6-sol': 'GPT-5.6' };

export function modelLabel(model: string | null | undefined): string {
  return (model && MODEL_LABELS[model]) || model || 'LLM';
}

/** Tab and badge detail for one LLM assessment: model, role, and score. */
export function llmRoleLabel(role: string, model: string | null | undefined, mode: Mode = 'retrospective'): string {
  const name = modelLabel(model);
  if (role === 'primary') return mode === 'prospective' ? `${name} · snapshot` : `${name} · primary`;
  if (role === 'previous_evaluation') return `${name} · previous primary`;
  if (role === 'reevaluation') return `${name} · re-evaluation`;
  return `${name} · re-run for the human comparison`;
}

export function evaluationTimingLabel(assessment: {
  source: Source;
  status: Status;
  evaluation_date?: string | null;
  publication_date?: string | null;
}): string {
  if (assessment.source === 'human') {
    if (assessment.status === 'available_in_open_pr' || assessment.status === 'in_progress') {
      return statusLabel(assessment.status, 'prospective', true);
    }
    if (assessment.evaluation_date) return assessment.evaluation_date;
    if (assessment.publication_date) return `Published ${assessment.publication_date}`;
  }
  return assessment.evaluation_date ?? 'Date not recorded';
}
