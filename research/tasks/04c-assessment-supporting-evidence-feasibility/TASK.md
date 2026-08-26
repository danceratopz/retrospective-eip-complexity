# Task 04c: Evaluate historical assessment-supporting evidence

## Objective

Determine whether historical snapshots of `ethereum/execution-specs` and `ethereum/execution-spec-tests` can safely add information to retrospective complexity assignments without importing post-cutoff knowledge or changing the proposal-time construct being measured.

This task evaluates supporting-evidence feasibility. It does not change Task 04 refs, score EIPs, estimate observed effort, inspect client implementations, or change Task 05 inputs, prompts, rubric files, outputs, or assessments.

## Inputs

- Every approved record under `research/tasks/04-complexity-assessment-ref-selection/outputs/fork-eips/`.
- `/home/dtopz/code/github/execution-specs`.
- `/home/dtopz/code/github/execution-spec-tests`.

Only Task 04 records with `review.status: approved` are in scope. Each record's `selection.information_cutoff_at` is the authoritative temporal boundary.

## Historical snapshot resolution

Resolve one snapshot per candidate repository and fork–EIP record with:

```text
git -C <repository> rev-list --first-parent -1 --before=<normalized-cutoff> <base-ref>
```

An ISO date without a time is normalized to `00:00:00Z`, matching the day-precision boundary used by Task 04. The `--first-parent` restriction is required because `execution-specs` imported EEST history as merge parents in 2025. Traversing all reachable parents can select a historical EEST-side commit that was not the `execution-specs` default-branch state at the cutoff. First-parent traversal reconstructs the public default-branch lineage while retaining the full tree introduced by each completed merge.

Inspect only the resolved commit's tree and blobs. Current paths may be used as post-cutoff navigation only when the output labels that use and the historical blob remains the evidence.

## Search protocol

For every repository snapshot:

1. Search the full path inventory for case-insensitive `eip`, optional separators, and the exact EIP number.
2. Search text blobs for case-insensitive references matching the exact EIP number.
3. Search reachable commit subjects through the snapshot for the EIP number, then inspect only paths that exist in the resolved snapshot.
4. Inspect fork-specific specification and test paths when a contemporaneous commit or explicit reference provides a defensible mapping despite the number not appearing in the current blob.
5. Record false positives, rejected paths, and negative-search limitations.

Generated fixtures and unrestricted repository trees are not candidate package evidence. Only exact source blobs may be considered for later allowlisting.

## Classification

Classify maturity separately for each repository–EIP pair as `absent`, `reference_only`, `scaffold`, `partial`, `substantively_informative`, or `uncertain`.

Classify methodological use separately as `exclude`, `provenance_only`, `uncertainty_context`, `supplementary_candidate`, or `primary_candidate`.

Historical presence, technical maturity, information gain, and methodological admissibility are independent fields. Implementation or tests that existed by the cutoff can still be inadmissible when they reveal completed work, encode decisions not established by the selected EIP blob, or make cross-fork scores incomparable.

## Outputs

```text
outputs/
├── repositories.yaml
├── fork-eips/
│   └── <fork>/eip-<number>.yaml
├── forks/
│   └── <fork>.yaml
└── feasibility-report.md
```

Each fork–EIP record contains both repository snapshots, complete search boundaries, exact relevant blob identities and hashes, maturity, methodological use, information gain, risks, confidence, and unknowns. Fork summaries count the two repository judgments separately.

## Reproduction

From the repository root:

```bash
python3 research/tasks/04c-assessment-supporting-evidence-feasibility/scripts/collect_outputs.py
python3 research/tasks/04c-assessment-supporting-evidence-feasibility/scripts/validate_outputs.py
```

The collector owns only this task's structured YAML. The feasibility report is a reviewed synthesis and is not overwritten by the collector.

## Acceptance criteria

- Every approved execution-affecting Task 04 record has one output containing both candidate repositories.
- Snapshot commits use the exact per-EIP cutoff and first-parent default-branch lineage.
- Every positive claim resolves to a historical blob with a full commit, Git blob SHA, SHA-256, and immutable URL.
- Every negative claim records its tree-wide search boundary and terms.
- Repository completeness and the EEST-to-EELS migration chronology are explicit.
- Maturity, information gain, and methodological use remain separate.
- Fork summary counts reproduce from the fork–EIP records.
- No Task 04 or Task 05 file is modified.
- `scripts/validate_outputs.py` passes.
