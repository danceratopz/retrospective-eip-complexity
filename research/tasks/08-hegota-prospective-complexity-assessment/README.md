# Hegotá prospective complexity assessment

Task 08 freezes the 44 proposals listed as PFI in Hegotá Meta EIP-8081 at one common EIPs repository snapshot and applies the Task 05 execution-layer rubric to every proposal for which that rubric is applicable.

Read `TASK.md` before acting. The top-level prompt intended for a coordinator LLM is `prompts/coordinator.md`. It tells the coordinator to implement the reusable adapter, prepare packages, launch isolated one-EIP assessors, validate and freeze outputs, and render the final cohort summary.

## Current state

- Task contract: complete
- Frozen source cohort: complete
- Cohort validator: complete
- Coordinator and isolated-assessor prompt templates: complete
- Layer/disposition review: complete and project-owner approved
- Shared Task 05 engine parameterization and 49-record regression: complete
- Package construction and byte-identical regeneration: complete
- Isolated assessment runs: complete, 37 of 37 validated
- Package and assessment hash freezes: complete
- Deterministic summaries: complete

The task deliberately stops numeric execution-layer scoring for consensus-only proposals. Those remain in the 44-entry cohort with explicit `not_applicable_to_el_rubric` records. A consensus-layer score requires a separately approved rubric.

## Validate the frozen cohort

Use the locked Task 05 environment because it already carries the YAML dependency:

```bash
uv run --project research/tasks/05-retrospective-complexity-assignment --locked \
  python research/tasks/08-hegota-prospective-complexity-assessment/scripts/validate_cohort.py \
  --eips-repo ../EIPs
```

This check uses only the local EIPs clone. It verifies the pinned commit, EIP-8081 blob and content hashes, PFI order, SFI/CFI exclusions, and the frontmatter of all 44 PFI EIPs.

## Delegate the full run

Give another capable filesystem-enabled coordinator LLM this file as its top-level instruction:

```text
/home/dtopz/code/github/retrospective-complexity-eval/research/tasks/08-hegota-prospective-complexity-assessment/prompts/coordinator.md
```

The coordinator must use the local EIPs and pm clones, must not fetch or browse, and must run each scoring session through the isolated capsule launcher. The source assessor prompt and contract are under `prompts/`; they are templates rendered into capsules, not prompts to run from the repository.

## Intended outputs

```text
outputs/
├── cohort-review.yaml
├── package-manifest.yaml
├── assessment-manifest.yaml
├── summary.yaml
├── summary.md
├── assessments/hegota-pfi-2026-08-26/
└── raw/hegota-pfi-2026-08-26/
```

These outputs were generated from the approved cohort review. `summary.md` is the human-readable result; `package-manifest.yaml` and `assessment-manifest.yaml` freeze the reproducible input and result hashes. The execution-layer-rubric total is explicitly limited to the 37 scored PFI proposals. Five consensus-only proposals and the two project-owner exclusions have no numeric score or tier.

## Reproduce the completed work unit

Use the locked Task 05 Python environment for the shared YAML dependency:

```bash
PYTHON=research/tasks/05-retrospective-complexity-assignment/.venv/bin/python
TASK=research/tasks/08-hegota-prospective-complexity-assessment

$PYTHON $TASK/scripts/validate_cohort.py --eips-repo ../EIPs
$PYTHON $TASK/scripts/validate_packages.py
$PYTHON $TASK/scripts/prepare_packages.py --verify-regeneration \
  --eips-repo ../EIPs --pm-repo ../pm
$PYTHON $TASK/scripts/finalize.py --summarize
```

`finalize.py --summarize` first verifies the assessment freeze against all 37 canonical records. It refuses to aggregate if a result is missing, invalid, or has changed since the freeze.
