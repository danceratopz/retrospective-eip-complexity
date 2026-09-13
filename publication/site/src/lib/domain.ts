/**
 * Domain model of the publication payload (schema 2.0.0) and pure accessors over it.
 *
 * Nothing here touches the filesystem, so both server-rendered components and client scripts can
 * import it. `data.js` owns loading.
 */

export type Source = 'llm' | 'human';
export type Mode = 'retrospective' | 'prospective';
export type Tier = 'low' | 'medium' | 'high';
export type Confidence = 'low' | 'medium' | 'high';
export type RubricRevision = 1 | 2;
export type Status =
  | 'complete'
  | 'available_in_open_pr'
  | 'in_progress'
  | 'incomplete'
  | 'not_applicable'
  | 'not_available';
export type ViewMode = 'llm' | 'human' | 'compare';

export interface Evidence {
  source: string;
  locator: string;
  summary: string;
}

export interface CriterionAssessment {
  id: string;
  score: number | null;
  rationale: string | null;
  evidence: Evidence[];
  confidence: Confidence | null;
  uncertainty_note: string | null;
  exceptional_score_justification: string | null;
  under_specified: boolean;
  interacting_eips?: number[];
  unidentified_interactions?: unknown[];
  raw_score_cell?: string;
  blank_interpretation?: string | null;
}

export interface UnderSpecification {
  present: boolean;
  summary: string | null;
  affected_criteria: string[];
  plausible_total_range: { minimum: number; maximum: number } | null;
  plausible_tiers: Tier[];
  unresolved_questions: string[];
}

export interface RevisionProvenance {
  repository: string;
  commit: string;
  path: string;
  committed_at: string | null;
  git_blob_sha: string | null;
  content_sha256: string | null;
  immutable_url: string;
  information_cutoff_at: string | null;
  current_revision_url: string;
  revision_history_url: string;
  note?: string;
}

export interface PullRequestRef {
  number: number;
  title: string;
  url: string;
  draft: boolean;
  updated_at?: string;
}

export interface SourceRecord {
  kind: 'research_record' | 'merged' | 'open_pull_request' | 'open_draft_pull_request';
  repository?: string;
  path?: string;
  commit?: string;
  committed_at?: string;
  git_blob_sha?: string;
  content_sha256?: string;
  immutable_url?: string;
  pull_request?: PullRequestRef;
  sha256?: string;
  branch?: string;
}

export interface Assessment {
  id: string;
  eip: number;
  title: string;
  fork: string;
  mode: Mode;
  source: Source;
  rubric_revision: RubricRevision;
  role: 'primary' | 'historical_rubric_rerun' | 'published_checklist';
  status: Status;
  scored: boolean;
  score: number | null;
  tier: Tier | null;
  confidence: Confidence | null;
  summary: string | null;
  criteria: CriterionAssessment[];
  under_specification: UnderSpecification | null;
  notable_ambiguities: string[];
  checklist?: {
    published_total: number | null;
    published_tier: Tier | null;
    recomputed_total: number | null;
    recomputed_tier: Tier | null;
    parser_notes: string[];
    unresolved_blank_rows?: string[];
    invalid_score_rows?: string[];
    missing_rows?: string[];
    input_alignment?: string | null;
    timing_exposure?: string | null;
  };
  provenance: {
    assessed_revision: RevisionProvenance | null;
    rubric: { revision: RubricRevision; repository: string; commit: string; path: string; immutable_url: string };
    assessor: { kind: Source; model?: string; reasoning_effort?: string; isolation_method?: string; organization?: string; publication?: string };
    source_record: SourceRecord;
    research_record?: { path: string; sha256: string };
    supporting_documents: string[];
  };
}

export interface HumanSummary {
  status: Status;
  assessment_id: string | null;
  score: number | null;
  tier: Tier | null;
  rubric_revision: RubricRevision | null;
  source_record: SourceRecord | null;
  other_candidates: Array<{
    availability: string;
    parse_state: string;
    rubric_revision: RubricRevision | null;
    recomputed_total: number | null;
    duplicates_preferred_scores: boolean;
    pull_request: PullRequestRef | null;
    immutable_url: string;
  }>;
  note: string | null;
}

export interface LlmSummary {
  status: Status;
  assessment_id: string | null;
  score: number | null;
  tier: Tier | null;
  confidence: Confidence | null;
  under_specified: boolean | null;
  information_cutoff_at: string | null;
  assessed_revision_at: string | null;
  exclusion_kind?: string;
  rationale?: string;
}

export interface Occurrence {
  id: string;
  eip: number;
  title: string;
  fork: string;
  fork_name: string;
  mode: Mode;
  layers: string[];
  snapshot_status: 'PFI' | 'SFI' | 'CFI' | null;
  scope_timing: 'included_at_cutoff' | 'added_after_cutoff' | null;
  llm: LlmSummary;
  human: HumanSummary;
  assessment_ids: string[];
  comparison_ids: string[];
  default_assessment_id: string | null;
}

export interface Eip {
  eip: number;
  title: string;
  forks: string[];
  default_fork: string;
  route: string;
  occurrences: Occurrence[];
}

export interface ComparisonRow {
  id: string;
  human: number;
  llm: number;
  delta: number;
  agreement: 'exact' | 'minor' | 'major';
}

export interface Comparison {
  id: string;
  eip: number;
  fork: string;
  rubric_revision: RubricRevision;
  human_assessment_id: string;
  llm_assessment_id: string;
  human_total: number;
  llm_total: number;
  delta: number;
  absolute_delta: number;
  human_tier: Tier;
  llm_tier: Tier;
  tier_agreement: boolean;
  rows: ComparisonRow[];
  agreement_counts: { exact: number; minor: number; major: number };
  largest_disagreements: string[];
  confounds: {
    clean_comparison: boolean;
    failed_conditions: string[];
    input_alignment: string;
    input_alignment_summary: string | null;
    template_match: string;
    human_timing_exposure: string;
    human_timing_exposure_rationale: string | null;
    primary_llm_total: number;
    cross_rubric_warning: string | null;
  } | null;
}

export interface CriterionDefinition {
  id: string;
  label: string;
  short_definition: string;
  anchors: Record<string, string>;
  notes: string[];
  rubric_revisions: RubricRevision[];
  uncapped: boolean;
  definition_present: boolean;
  revision_1_anchors?: Record<string, string>;
}

export interface TierThresholds {
  low: { minimum: number; maximum: number };
  medium: { minimum: number; maximum: number };
  high: { minimum: number; maximum: null };
}

export interface Rubric {
  revision: RubricRevision;
  criteria: string[];
  criterion_count: number;
  nominal_maximum: number;
  tier_thresholds: TierThresholds;
  source: { repository: string; commit: string; path: string; immutable_url: string; checklist_revision: number; known_source_defects?: string[] };
}

export interface CompositionBlock {
  assessment_count: number;
  rubric_revision: RubricRevision | null;
  score_sum: number;
  criteria: Array<{ id: string; score_sum: number; eip_count: number }>;
}

export interface ForkSummary {
  fork: string;
  name: string;
  short_name: string;
  mode: Mode;
  eip_count: number;
  scored_count: number;
  not_applicable_count: number;
  final_scope_score_sum: number;
  at_cutoff_count: number | null;
  at_cutoff_score_sum: number | null;
  late_addition_count: number | null;
  late_addition_score_sum: number | null;
  score_sum: number;
  composition: Record<string, CompositionBlock>;
  human_coverage: { status_counts: Record<Status, number>; scored_count: number; comparable_count: number };
}

export interface Publication {
  schema_version: string;
  release_state: string;
  criteria: CriterionDefinition[];
  rubrics: Record<string, Rubric>;
  eips: Eip[];
  assessments: Record<string, Assessment>;
  comparisons: Record<string, Comparison>;
  forks: ForkSummary[];
  hegota: any;
  fork_shipping: any;
  human_llm: {
    fork: string;
    rubric_revision: RubricRevision;
    rows: Array<{
      eip: number;
      title: string;
      comparison_id: string;
      human_assessment_id: string;
      llm_assessment_id: string;
      human_total: number;
      llm_total: number;
      delta: number;
      human_tier: Tier;
      llm_tier: Tier;
      tier_agreement: boolean;
      clean: boolean;
      primary_llm_assessment_id: string | null;
      primary_llm_total: number | null;
      input_alignment: string | null;
      human_timing_exposure: string | null;
    }>;
    summary: {
      comparison_count: number;
      clean_count: number;
      mean_signed_delta: number;
      mean_absolute_delta: number;
      median_absolute_delta: number;
      llm_higher_count: number;
      human_higher_count: number;
      equal_total_count: number;
      tier_agreement_count: number;
    };
    criteria: Array<{ id: string; mean_delta: number; mean_absolute_delta: number; llm_higher_count: number; human_higher_count: number; exact_count: number; nonzero_count: number }>;
  };
  charts: Record<string, string>;
}

export const FORK_ORDER = ['shanghai', 'cancun', 'prague', 'osaka', 'amsterdam', 'hegota'];

export function allOccurrences(data: Publication): Occurrence[] {
  return data.eips.flatMap((eip) => eip.occurrences);
}

export function findEip(data: Publication, eip: number): Eip | undefined {
  return data.eips.find((item) => item.eip === eip);
}

export function findOccurrence(data: Publication, eip: number, fork: string): Occurrence | undefined {
  return findEip(data, eip)?.occurrences.find((item) => item.fork === fork);
}

export function assessmentsFor(data: Publication, occurrence: Occurrence): Assessment[] {
  return occurrence.assessment_ids.map((id) => data.assessments[id]);
}

export function primaryAssessment(data: Publication, occurrence: Occurrence): Assessment | null {
  return occurrence.llm.assessment_id ? data.assessments[occurrence.llm.assessment_id] : null;
}

export function humanAssessment(data: Publication, occurrence: Occurrence): Assessment | null {
  return occurrence.human.assessment_id ? data.assessments[occurrence.human.assessment_id] : null;
}

export function comparisonsFor(data: Publication, occurrence: Occurrence): Comparison[] {
  return occurrence.comparison_ids.map((id) => data.comparisons[id]);
}

/** The assessment views an occurrence supports; Human and Compare appear only when the data exists. */
export function viewModes(occurrence: Occurrence): ViewMode[] {
  const modes: ViewMode[] = [];
  if (occurrence.llm.assessment_id) modes.push('llm');
  if (occurrence.human.assessment_id) modes.push('human');
  if (occurrence.comparison_ids.length) modes.push('compare');
  return modes;
}

export function defaultView(occurrence: Occurrence): ViewMode | null {
  return viewModes(occurrence)[0] ?? null;
}

export function rubricFor(data: Publication, revision: RubricRevision): Rubric {
  return data.rubrics[String(revision)];
}

export function criterionDefinition(data: Publication, id: string): CriterionDefinition {
  const definition = data.criteria.find((item) => item.id === id);
  if (!definition) throw new Error(`Unknown criterion ${id}`);
  return definition;
}

export function registryIndex(data: Publication): Map<string, number> {
  return new Map(data.criteria.map((item, index) => [item.id, index]));
}

/**
 * Site-wide criterion ordering for an assessment's rows: non-zero first, highest score first, then the
 * stable registry order. Returns the two partitions so zero rows can be collapsed.
 */
export function partitionCriteria(
  assessment: Assessment,
  order: Map<string, number>,
): { nonZero: CriterionAssessment[]; zero: CriterionAssessment[]; unresolved: CriterionAssessment[] } {
  const stable = (item: CriterionAssessment) => order.get(item.id) ?? Number.MAX_SAFE_INTEGER;
  const scored = assessment.criteria.filter((item) => item.score !== null);
  const unresolved = assessment.criteria.filter((item) => item.score === null).sort((a, b) => stable(a) - stable(b));
  const nonZero = scored
    .filter((item) => (item.score ?? 0) > 0)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0) || stable(a) - stable(b));
  const zero = scored.filter((item) => item.score === 0).sort((a, b) => stable(a) - stable(b));
  return { nonZero, zero, unresolved };
}

export function topDrivers(assessment: Assessment, order: Map<string, number>, limit = 4): CriterionAssessment[] {
  return partitionCriteria(assessment, order).nonZero.slice(0, limit);
}

export function tierFor(score: number, thresholds: TierThresholds): Tier {
  if (score >= thresholds.high.minimum) return 'high';
  if (score >= thresholds.medium.minimum) return 'medium';
  return 'low';
}

/** Human-readable score bands for one rubric revision, e.g. { low: '<12', medium: '12–22', high: '≥23' }. */
export function scoreBands(thresholds: TierThresholds): Record<Tier, string> {
  return {
    low: `<${thresholds.medium.minimum}`,
    medium: `${thresholds.medium.minimum}–${thresholds.medium.maximum}`,
    high: `≥${thresholds.high.minimum}`,
  };
}

export function forkSummary(data: Publication, fork: string): ForkSummary {
  const summary = data.forks.find((item) => item.fork === fork);
  if (!summary) throw new Error(`Unknown fork ${fork}`);
  return summary;
}

/** Sum criterion scores across scored assessments that share one rubric revision. */
export function aggregateComposition(assessments: Assessment[], order: Map<string, number>): CompositionBlock {
  const totals = new Map<string, { score_sum: number; eip_count: number }>();
  const revisions = new Set(assessments.map((item) => item.rubric_revision));
  if (revisions.size > 1) throw new Error('aggregateComposition requires one rubric revision');
  for (const assessment of assessments) {
    if (!assessment.scored) continue;
    for (const criterion of assessment.criteria) {
      const bucket = totals.get(criterion.id) ?? { score_sum: 0, eip_count: 0 };
      bucket.score_sum += criterion.score ?? 0;
      if ((criterion.score ?? 0) > 0) bucket.eip_count += 1;
      totals.set(criterion.id, bucket);
    }
  }
  return {
    assessment_count: assessments.filter((item) => item.scored).length,
    rubric_revision: revisions.size ? [...revisions][0] : null,
    score_sum: assessments.reduce((sum, item) => sum + (item.score ?? 0), 0),
    criteria: [...totals.entries()]
      .sort((a, b) => (order.get(a[0]) ?? 0) - (order.get(b[0]) ?? 0))
      .map(([id, bucket]) => ({ id, ...bucket })),
  };
}
