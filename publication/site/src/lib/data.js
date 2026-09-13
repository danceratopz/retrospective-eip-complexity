import fs from 'node:fs';
import path from 'node:path';

const dataPath = path.resolve(process.cwd(), 'public/generated/publication.json');
let cached = null;

export function loadPublication() {
  if (!cached) cached = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
  return cached;
}

export function basePath(value = '') {
  const normalized = value.replace(/^\/+/, '');
  return `/retrospective-eip-complexity/${normalized}`;
}

/** Flatten every EIP occurrence, in fork order, with its primary (LLM) assessment attached. */
export function occurrences(data = loadPublication()) {
  return data.eips.flatMap((eip) => eip.occurrences.map((occurrence) => ({
    ...occurrence,
    primary: occurrence.llm.assessment_id ? data.assessments[occurrence.llm.assessment_id] : null,
  })));
}

/**
 * Transitional projection of the schema 2.0.0 payload onto the row shape the original page templates
 * expect. It disappears once every page reads the domain model directly.
 */
export function legacyAssessmentRows(data = loadPublication()) {
  return occurrences(data).map((occurrence) => {
    const primary = occurrence.primary;
    const revision = primary?.provenance.assessed_revision;
    return {
      assessment_route: occurrence.mode === 'prospective' ? `prospective/hegota/#eip-${occurrence.eip}` : `forks/${occurrence.fork}/eips/${occurrence.eip}/`,
      assessed_revision: revision?.commit,
      assessed_revision_at: revision?.committed_at,
      assessed_revision_url: revision?.immutable_url,
      current_revision_url: revision?.current_revision_url,
      revision_history_url: revision?.revision_history_url,
      confidence: occurrence.llm.confidence,
      criteria: primary ? primary.criteria.map((criterion) => ({ id: criterion.id, score: criterion.score })) : [],
      eip: occurrence.eip,
      fork: occurrence.fork,
      layers: occurrence.layers,
      mode: occurrence.mode,
      score: occurrence.llm.score,
      scope_timing: occurrence.scope_timing,
      snapshot_status: occurrence.snapshot_status,
      status: primary ? 'scored' : 'not_applicable',
      summary: primary ? primary.summary : occurrence.llm.rationale,
      rationale: primary ? undefined : occurrence.llm.rationale,
      tier: occurrence.llm.tier,
      title: occurrence.title,
      under_specification: occurrence.llm.under_specified,
      under_specification_summary: primary ? primary.under_specification.summary : null,
    };
  });
}
