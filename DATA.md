# Data and provenance

## Canonical records

YAML is the canonical research format. Canonical records include:

- fork membership and fork–EIP relationships;
- global EIP creation, revision, and dependency histories;
- per-observation source registries;
- fork milestones and per-EIP devnet participation;
- proposed and approved assessment refs;
- proposed and approved fork evaluation cutoffs and aggregation cohorts;
- sealed historical assessment packages;
- original retrospective complexity assignments;
- frozen prospective fork-cohort snapshots and reviewed layer dispositions; and
- isolated prospective complexity assignments in their task-specific namespace.

Dates use quoted ISO 8601 values. Every factual observation must reference a source ID or be explicitly marked unknown. Git evidence records the repository, full commit SHA, path, and immutable permalink. Selected assessment refs additionally record the Git blob SHA and content SHA-256.

## Raw evidence

Mutable GitHub, HackMD, and web evidence is captured under the owning task's `raw/` directory when redistribution permits. Source registries record retrieval time, archive path, content hash, and redistribution status. Large recordings and material with unclear redistribution rights remain reference-only with a precise locator.

Git content normally is not duplicated as raw data because repository, commit, path, and immutable URL reproduce the exact blob and diff.

## Derived and generated artifacts

The following are derived from canonical records and may be regenerated:

- normalized plot data;
- Vega-Lite specifications;
- offline HTML figures;
- SVG and PDF figures;
- plot manifests;
- fork-cutoff review timelines;
- generated Task 05 prompts and sealed packages; and
- generated Task 08 one-EIP prompts, packages, freeze manifests, and summaries.

Generated artifacts are retained in this initial snapshot because they make review convenient and their manifests permit direct hash comparison. They must never be edited by hand.

## Agent-produced evidence

Task 04 ref proposals, Task 04b cutoff/cohort proposals, Task 05 complexity assignments, and Task 08 layer dispositions and prospective assignments are agent-produced research records. Their provenance includes the task contract, inputs, selected historical content or common snapshot, rationale, confidence, unknowns, and review state.

Validated raw and canonical assessment YAML is versioned. Verbose Task 05 and Task 08 console transcripts are excluded from Git because they contain machine-specific paths and local Codex session identifiers. They are operational diagnostics rather than scoring evidence.

## Publication boundary

Before adding a remote or publishing a release:

1. review every raw source's redistribution status;
2. scan the full Git history for credentials and private operational metadata;
3. decide whether local assessment session identifiers should be replaced with publication-safe run identifiers;
4. add an explicit license for repository-authored code and data; and
5. document any upstream material governed by a different license.
