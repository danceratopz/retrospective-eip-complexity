# Task 08: Assess the Hegotá PFI cohort prospectively

## Objective

Apply the same execution-layer complexity rubric used by Task 05 to the Hegotá proposals that were Proposed for Inclusion (PFI) in EIP-8081 at the common snapshot captured on 2026-08-26. Produce one isolated, immutable assessment for every proposal to which the execution-layer rubric applies, and an explicit not-applicable record for every consensus-only proposal.

This task is a prospective snapshot study. It asks what the current proposals imply at one shared evaluation horizon. It does not reconstruct proposal-time history, predict the eventual Hegotá scope, assess EIPs added after the snapshot, or treat consensus-only proposals as zero-complexity execution changes.

## Frozen cohort and snapshot

The authoritative source inventory is `inputs/hegota-pfi-2026-08-26.yaml`.

- Fork: Hegotá
- Meta EIP: EIP-8081
- Cohort section: `Proposed for Inclusion`
- Snapshot ID: `hegota-pfi-2026-08-26-ac450a4`
- EIPs repository commit: `ac450a4ab2f37387385ee9c54b62f518d97e6cc9`
- Snapshot commit time: `2026-08-25T11:56:58Z`
- Captured on: `2026-08-26`
- PFI entries: 44, in source order
- Excluded from this cohort: EIP-7805 (SFI) and EIP-8141 (CFI)

The common EIPs repository commit is the information cutoff for the primary EIP and every same-repository supporting EIP. The `captured_on` date identifies the research snapshot; it must not be substituted for the source commit time.

Changing the EIP-8081 PFI list or selecting a later EIPs commit defines a new snapshot. Create a new manifest, package tree, output tree, and snapshot ID; never rewrite this cohort in place.

## Relationship to the retrospective study

Task 08 is a separate prospective branch of the research stack. It reuses Task 05's assessment construct, rubric, package format, isolation boundary, model settings, and mechanical scoring validation, but does not enter the 49-row retrospective dataset or Task 07 prediction–outcome analysis.

```text
Task 05 retrospective assessment engine
    |
    +--> historical Task 04 refs --> 49 retrospective outputs
    |
    +--> Task 08 common snapshot --> Hegotá prospective outputs
```

All Task 08 artifacts require a distinct `task_id`, snapshot provenance, and task-owned paths. A Task 08 result must never overwrite, masquerade as, or be aggregated with a Task 05 result.

## Rubric and assessor settings

Reuse these Task 05 pins exactly so results remain comparable:

- model: `gpt-5.6-sol`
- reasoning effort: `xhigh`
- rubric repository: `ethspecs/pm`
- rubric commit: `3d8c0128c5543dd3146341ef395aa344e4abea30`
- rubric path: `Templates/EIP-Complexity-Assessment.md`
- rubric Git blob: `b0d2258a8fdd1a514b61ef42ab0fd5a6d7fb5046`
- rubric content SHA-256: `16da70eafc61ca7ff9be62b4a89017f4a881a6ff3a27bb02040334d3100dba2a`
- checklist revision: 2
- assessor-view transformation: `remove_revision_notes_and_calibration_examples_v1`
- isolation: one fresh bubblewrap capsule per EIP
- maximum concurrent assessors: 3

"Today's ref" applies to the Hegotá EIP snapshot, not to the rubric. Updating the rubric would confound snapshot results with a checklist change and requires a separate labelled study.

## Required reuse and implementation boundary

Do not create a second, drifting implementation of the 28-criterion assessment engine. Before building Task 08 packages, extract or parameterize the task-agnostic portions of Task 05:

- rubric verification and assessor-view construction;
- linked-EIP discovery and package materialization;
- manifest and file hashing;
- output-template construction;
- sealed-package validation;
- bubblewrap capsule creation and session launch;
- raw-output recovery without semantic repair;
- assessment validation, score summation, and tier calculation; and
- bounded-concurrency orchestration.

Thin Task 05 and Task 08 adapters may supply their task root, task ID, fork/snapshot metadata, input-ref policy, prompt paths, and output paths. Shared code must preserve Task 05 behavior byte-for-byte. Before any Task 08 run, all 49 existing Task 05 packages and outputs must still validate and every tracked Task 05 package/output hash must remain unchanged.

If safe extraction is materially riskier than parameterizing the existing scripts, prefer the smaller parameterization. Copy-pasting the scripts into Task 08 is not acceptable.

## Cohort review and layer disposition

The source manifest freezes membership but intentionally does not guess assessment applicability. Before package construction, create `outputs/cohort-review.yaml` with one entry for every frozen PFI EIP in the same order.

Each entry must record:

- EIP number and canonical title;
- affected layers: `execution`, `consensus`, or both;
- disposition: `score_el_rubric` or `not_applicable_to_el_rubric`;
- a proposal-text locator and concise rationale;
- reviewer, review date, confidence, and status; and
- any ambiguity requiring owner input.

Execution-only, cross-layer, and execution-client networking changes use `score_el_rubric`. Cross-layer scores cover only the execution-layer surface. Consensus-only proposals use `not_applicable_to_el_rubric`; they must receive an explicit disposition record and no numeric score or tier. Do not represent not-applicable proposals as zero.

Every one of the 44 cohort entries must have `review.status: approved` before packages are built. Stop for project-owner review if an entry is ambiguous. A separate consensus-layer rubric and study are required to produce CL complexity scores; Task 08 must not invent one.

## Evidence package

For each `score_el_rubric` entry, build a deterministic sealed package:

```text
inputs/packages/hegota-pfi-2026-08-26/eip-<number>/
├── manifest.yaml
├── eip.md
├── rubric.md
├── output-template.yaml
└── supporting/
```

The primary `eip.md` is exactly `EIPS/eip-<number>.md` at the frozen common commit. Include only:

- directly required or directly linked EIPs from the same EIPs commit; and
- directly linked external documents whose immutable commit, content, availability at the snapshot, relevance, and admissibility can be mechanically verified.

Reuse Task 05's conservative primary-evidence policy. Links to `execution-specs` or `execution-spec-tests` remain provenance-only and do not enter `assessment_source_files`. Mutable URLs, implementation repositories, tests, devnets, discussion outcomes, prior assessments, and present or future fork results are prohibited. A URL in a sealed source is not permission to browse.

Every package manifest must record the cohort-manifest identity and hash, common EIPs snapshot, primary EIP blob and content hash, rubric provenance, supporting-document allowlist, assessment-source order, source policy, preparation script, task contract, prompt, and all materialized file hashes.

## Prospective information firewall

Each assessor sees one proposal only. It may read `PROMPT.md`, `ASSESSMENT-CONTRACT.md`, the package manifest and template, the pinned rubric, the primary EIP, and the exact allowlisted supporting files. It may write only `/mnt/workspace/assessment.yaml`.

The assessor must not access:

- the internet, browsers, network commands, apps, plugins, MCP servers, or skills;
- the repository, vault, coordinator state, cohort review, or aggregate progress;
- another Hegotá proposal or package except a supporting EIP sealed in its allowlist;
- Task 05 results, Task 07 metrics, human assessments, calibration data, or prior Task 08 results;
- any post-snapshot EIP text or source;
- implementations, tests, devnets, client discussions, fork decisions, outcomes, or observed effort; or
- latent knowledge as assessment evidence.

If prohibited information is exposed, mark the run contaminated, preserve the raw output, reject it as authoritative, and rerun only in a demonstrably fresh clean capsule. Never semantically repair a score outside the isolated assessor.

## Assessment method and output

Reuse Task 05's complete 28-criterion method, evidence-entry schema, rubric order, exceptional-score rule, cross-EIP representation, under-specification treatment, total calculation, tier thresholds, confidence vocabulary, and raw-recovery boundary.

Task 08 output paths are:

```text
outputs/assessments/hegota-pfi-2026-08-26/eip-<number>.yaml
outputs/raw/hegota-pfi-2026-08-26/eip-<number>.yaml
```

The Task 08 schema must replace retrospective identity with:

- `task_id: 08-hegota-prospective-complexity-assessment`;
- `fork_id: hegota`;
- `snapshot_id: hegota-pfi-2026-08-26-ac450a4`;
- `assessment.snapshot_scope_summary` rather than `historical_scope_summary`;
- `provenance.cohort_snapshot` and `provenance.snapshot_eip`; and
- `information_control` attesting to no post-snapshot or prohibited exposure.

Do not retain misleading historical field names merely to avoid a small schema adapter. The shared validator may normalize both schemas internally, but persisted Task 08 records must describe the prospective construct accurately.

## Orchestration and freeze order

The coordinator must preserve this order:

1. Validate the frozen EIP-8081 cohort against the exact EIPs commit.
2. Complete and validate the human-approved layer/disposition review.
3. Implement the shared-engine adapter and pass the Task 05 regression gate.
4. Build and validate all Task 08 packages deterministically.
5. Write `outputs/package-manifest.yaml` containing the ordered package inventory and hashes.
6. Require byte-identical package regeneration before starting an assessor.
7. Run one fresh isolated session per scorable EIP, with at most three concurrent sessions.
8. Validate and import each result without overwriting an existing canonical output.
9. Freeze all canonical assessment and raw-output hashes in `outputs/assessment-manifest.yaml`.
10. Only after the freeze, render `outputs/summary.md` and `outputs/summary.yaml`.

No partial score or aggregate may be passed into a pending assessor session. The orchestrator may report completion counts while runs are active, but not scores, tiers, or rankings.

## Aggregation and reporting

The summary must report:

- snapshot identity and common information cutoff;
- 44 total PFI entries;
- scorable execution/cross-layer count and consensus-only not-applicable count;
- completion and validation counts;
- one row per scorable EIP with score, tier, confidence, under-specification, and affected layers;
- one row per not-applicable EIP with its disposition rationale;
- sum of scorable EL-rubric totals, with an explicit numerator and denominator;
- tier, confidence, and under-specification distributions; and
- caveats about proposal splitting, overlapping interactions, scope churn, and the lack of CL scores.

Never publish an unlabeled "Hegotá total" that appears to cover all protocol complexity. Use wording such as `EL-rubric total: X across N scored PFI EIPs; M consensus-only PFI EIPs not applicable`.

## Stop conditions

Stop and request project-owner input if:

- the pinned EIP-8081 blob does not yield exactly the frozen ordered 44-entry PFI cohort;
- a source EIP is absent at the pinned commit or its frontmatter conflicts with the manifest;
- layer applicability remains ambiguous after reading the snapshot proposal;
- a required external dependency cannot be pinned as snapshot-admissible;
- Task 05 regression validation or byte-preservation fails;
- the rubric pin or transformed assessor view differs from Task 05;
- clean bubblewrap/network isolation cannot be established;
- an existing canonical Task 08 output would need to be overwritten; or
- contamination cannot be confined to a clearly identified disposable run.

## Acceptance criteria

- The frozen cohort validator proves the exact EIP-8081 source, section, order, count, exclusions, and per-EIP frontmatter.
- All 44 entries have approved, evidence-backed layer and disposition records.
- Every scorable entry has one deterministic sealed package and one uncontaminated mechanically valid assessment.
- Every consensus-only entry has an explicit not-applicable record and no score or tier.
- The exact Task 05 rubric, assessor view, model, reasoning effort, and isolation standard are reused.
- All 49 Task 05 inputs and outputs still validate and remain byte-identical.
- Package and assessment freeze manifests reproduce deterministically.
- The summary recomputes from frozen canonical records and labels its denominator and N/A population.
- No Task 08 result enters the Task 05 or Task 07 datasets.
- Task-owned files and any minimal shared-engine changes are committed locally without staging unrelated changes; nothing is pushed.
