# Run the Hegotá PFI prospective complexity assessments

Work locally in `/home/dtopz/code/github/retrospective-complexity-eval`.

Read these files completely before acting:

- `/home/dtopz/code/github/retrospective-complexity-eval/research/tasks/08-hegota-prospective-complexity-assessment/TASK.md`
- `/home/dtopz/code/github/retrospective-complexity-eval/research/tasks/08-hegota-prospective-complexity-assessment/README.md`
- `/home/dtopz/code/github/retrospective-complexity-eval/research/tasks/08-hegota-prospective-complexity-assessment/inputs/hegota-pfi-2026-08-26.yaml`
- `/home/dtopz/code/github/retrospective-complexity-eval/research/tasks/05-retrospective-complexity-assignment/TASK.md`
- `/home/dtopz/code/github/retrospective-complexity-eval/research/tasks/05-retrospective-complexity-assignment/README.md`

Use `/home/dtopz/code/github/EIPs` as the canonical local EIP source and `/home/dtopz/code/github/pm` as the canonical local rubric source. Use only the commits pinned by the Task 08 contract and source manifest. Do not browse, fetch, pull, or substitute a current branch tip.

Implement and execute the self-contained Task 08 work unit. First validate the 44-entry EIP-8081 PFI snapshot. Then create the complete evidence-backed layer/disposition review in source order. Execution-only, cross-layer, and execution-client networking proposals are eligible for the existing execution-layer rubric; consensus-only proposals must receive explicit `not_applicable_to_el_rubric` records and no numeric score. Stop for project-owner review if applicability is ambiguous or the task's required approval gate cannot be satisfied faithfully.

Reuse Task 05's assessment engine rather than copying it. Extract or parameterize only the task-agnostic package, validation, isolation, recovery, and orchestration logic, with thin task adapters. Before running any Task 08 assessor, prove that all 49 existing Task 05 packages and outputs still validate and that no tracked Task 05 package or output byte changed.

Build every Task 08 package from EIP text at EIPs commit `ac450a4ab2f37387385ee9c54b62f518d97e6cc9`. Use the exact Task 05 checklist-revision-2 rubric and assessor view. Include only directly required, same-snapshot EIPs and explicitly admissible immutable supporting documents. Treat execution-specs and execution-spec-tests links as provenance-only. Generate and validate packages deterministically, freeze their hashes, and require byte-identical regeneration before launching an assessor.

Run one fresh `gpt-5.6-sol` assessor at `xhigh` per scorable EIP through a bubblewrap one-EIP capsule, with at most three concurrent sessions. Render `prompts/assessor.md` and `prompts/ASSESSMENT-CONTRACT.md` into each capsule with its sole assigned identity. Each assessor must see only its operational files and sealed package, have no network or repository access, and write only `/mnt/workspace/assessment.yaml`. Do not expose cohort results, prior scores, implementations, tests, discussions, post-snapshot text, other packages, skills, plugins, apps, MCP servers, or project-management records.

Validate and import each assessment without overwriting an existing canonical result. Preserve raw outputs for structurally recoverable formatting failures, never semantically repair a score, and reject contaminated sessions. Freeze the canonical result hashes before any aggregation. Pending assessor sessions must never receive partial scores or aggregates.

After the freeze, generate deterministic YAML and Markdown summaries. Report the execution-layer-rubric total with an explicit scored denominator and separate not-applicable count; never imply that it is the total complexity of all Hegotá protocol work. Keep Task 08 outputs separate from the 49 retrospective Task 05 records and the Task 07 prediction–outcome dataset.

Preserve unrelated working-tree changes. Commit only Task 08 files and the minimal shared-engine/documentation changes required by the contract after every validator and regression check passes. Do not push.

Persist until the approved cohort review, sealed packages, isolated assessments, freeze manifests, validation report, and summaries are complete, or a stop condition in `TASK.md` requires project-owner input.
