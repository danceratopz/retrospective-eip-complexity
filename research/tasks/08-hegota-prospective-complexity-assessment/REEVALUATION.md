# Hegotá evaluation history, version 1

This contract extends [Task 08](TASK.md) for evaluations after the original freeze.
The original contract, packages, assessments, and freeze manifests remain immutable.
Task 05 retrospective cutoffs through Amsterdam and Task 07 inputs remain unchanged.

## New evaluations

A new evaluation may cover one previously assessed EIP or a selected cohort. Pin the
latest intended EIPs revision to a full commit before preparation; never evaluate a
moving branch. Each batch has a unique snapshot ID and its own directory under
`evaluations/<snapshot-id>/`, containing `cohort.yaml`, `review.yaml`, packages,
prompts, raw outputs, assessments, and package and assessment freeze manifests.
A partial batch is a selected cohort, not a complete Hegotá snapshot.

The cohort uses the original Task 08 manifest shape, with an explicit inventory and
PFI, CFI, or SFI status per entry at that commit. The review uses the original review
shape and requires approved applicability decisions for every selected entry.
Missing or ambiguous applicability stops preparation. Consensus-only entries remain
not applicable and never receive a numeric score.

Reuse the pinned rubric, model, reasoning effort, source policy, and fresh isolated
assessment engine from Task 08. An assessor must not see original scores, human
checklists, or another evaluation. A rubric or model change requires a separately
labelled study. Validate packages, prove deterministic regeneration, run isolated
assessors, validate results, and freeze their hashes before publication. Never
replace an existing canonical assessment; a retry after publication needs a new ID.

## Registry and publication

`outputs/evaluation-registry.yaml` is the append-only publication inventory. Original
entries retain their existing public IDs. New entries add `:<snapshot-id>` to the
original `hegota:<eip>:llm:r2` identity. Entries record snapshot identity, EIP, inclusion
status, assessment path and hash, and the assessment freeze path and hash. New
entries must reference a successfully validated, frozen batch. Only explicitly
registered complete assessments are published; packages and operational records are
never public. New candidates need a separate membership/publication extension;
this revision supports re-evaluation of the existing 46 candidates.

Evaluation dates are derived from the recorded assessor `run_at` timestamp, normalized
to UTC when an offset is recorded; historical date-only values retain their precision.
They are distinct from capture dates and spec commit dates. Missing historical
timestamps remain unknown. No build-time clock is used. Human checklist commit and
pull-request dates must not be described as evaluation dates.

All registered evaluations appear in the history and table. Each has a stable URL.
The original August cohort remains the explicitly selected aggregation snapshot:
new evaluations do not change its totals, composition, or Human-versus-LLM pairs.
The comparison tool can compare any selected versions, including versions of one EIP.
A future latest-per-EIP aggregate must label its mixed dates and membership policy;
never sum historical and updated evaluations together as fork complexity.
