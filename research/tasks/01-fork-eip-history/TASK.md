# Task 01: Reconstruct fork membership and EIP histories

## Objective

Produce an auditable inventory of the EIPs associated with each fork and a reusable historical record for every unique EIP.

This task has two independent work-unit types:

1. A **fork work unit** reconstructs authoritative fork membership, affected-layer classifications, and inclusion-state events.
2. An **EIP work unit** reconstructs one EIP's creation and complete revision history.

The two output sets are joined later by EIP number. An EIP that appears in multiple forks must have only one global EIP-history record.

This task gathers evidence. It does not research client implementation history or devnet participation, choose a retrospective assessment date, score complexity, or judge how difficult an EIP proved to ship.

## Inputs

### Fork work unit

Each fork run receives exactly one file from `inputs/`. Treat its fork-membership sources and section rules as the authoritative definition of that fork's EIP set.

At the start of the run, resolve every moving Git reference to an exact commit and record it in the output. Never report evidence from an unrecorded repository state.

### EIP work unit

Each EIP run receives exactly one EIP number from the union of the reviewed fork inventories. It may also receive paths to the relevant fork–EIP records as discovery context.

Run this work unit once per unique EIP, not once per fork occurrence. If an output already exists, do not overwrite it or conduct a second independent history reconstruction without an explicit verification assignment.

## Scope

### Fork work unit

1. Inventory every EIP selected by the fork input's membership rules.
2. Classify each EIP's affected layers as `execution`, `consensus`, or both. Use `layers: [execution, consensus]` for cross-layer EIPs; do not force them into one layer.
3. Reconstruct every supported inclusion-state event relevant to each fork–EIP relationship.
4. Preserve the source document's distinction between core, other, networking, informational, optional, and scheduled EIPs. Do not silently treat every EIP mentioned by a Meta EIP as an included protocol change.
5. Do not inspect every revision of the individual EIP file; that belongs to the EIP work unit.

### EIP work unit

1. Record the EIP's declared creation date and earliest repository commit.
2. Review every commit that changes `EIPS/eip-<number>.md`.
3. Classify every revision, including editorial and ambiguous changes.
4. Derive simple revision aggregates, including first and last revision dates.
5. Record explicit cross-EIP dependency events and how they change over time.
6. Do not reconstruct fork membership or duplicate inclusion-state research from a fork work unit.

### Out of scope

- client implementation history;
- devnet membership or participation;
- assessment-date selection;
- complexity scoring; and
- observed-development-complexity judgments.

## Definitions

### EIP creation

Record both:

- the EIP frontmatter `created` date; and
- the earliest Git commit that added the EIP file.

Explain any discrepancy. The Git event is the earliest independently verifiable repository event, while the frontmatter date is the proposal's declared creation date.

### Inclusion-state event

Preserve the exact historical term in `raw_label` and separately normalize it when possible to one of:

- `proposed_for_inclusion`;
- `considered_for_inclusion`;
- `removed_from_consideration`;
- `scheduled_for_inclusion`;
- `removed_from_schedule`;
- `declined_for_inclusion`;
- `included`; or
- `unknown`.

Do not impose current CFI/SFI vocabulary retroactively when an older source used a different decision process. Explain the mapping in `normalization_rationale`; use `unknown` when the historical term does not map cleanly.

An EIP can enter consideration or scheduling more than once. Preserve the complete sequence and derive normalized-state counts from the event list. Do not infer a transition solely from a later summary saying that it happened; search for the contemporaneous decision or repository change. When no primary evidence can be found, record the search performed and mark the event or date `unknown`.

### EIP revision

Review every commit that changes `EIPS/eip-<number>.md` and record one event per commit. Count post-creation Git commits, not dates, as revision events.

The initial commit that adds the file is `event_kind: creation`. Every later file-changing commit is `event_kind: revision`. `file_commit_count` includes the creation event; revision counts and first/last revision dates exclude it. This distinction must remain explicit.

Record both `change_type` and `semantic_effect`:

- `change_type` describes what changed: `normative_behavior`, `parameter`, `interface_or_data_structure`, `dependency`, `security_assumption`, `clarification`, `editorial`, or `uncertain`.
- `semantic_effect` is `substantive`, `non_substantive`, or `uncertain`.

A revision is substantive when it changes or materially clarifies normative behavior, parameters, interfaces, data structures, dependencies, security assumptions, or another detail that could affect implementation or testing.

Typographical, grammatical, formatting, link-only, author-metadata, and other non-semantic changes are normally `editorial` with `semantic_effect: non_substantive`. Preserve them so the output demonstrates that every file-changing commit was reviewed. Do not silently exclude an ambiguous change: mark it `uncertain` and explain why.

If one logical update spans multiple commits, preserve every commit and add a shared `change_group` identifier so later analysis can aggregate it without losing provenance.

Derive the following directly from the event list:

- file-commit count;
- total post-creation revision count;
- substantive, non-substantive, and uncertain revision counts;
- first and last revision dates; and
- first and last substantive revision dates.

Store the event IDs used to derive the summary so the aggregates can be mechanically validated.

### Explicit cross-EIP dependency

Record a dependency only when the EIP text or another primary source explicitly identifies another EIP. Do not infer architectural coupling in this task.

Preserve dependency changes as events rather than storing only the final list. Each event records the target EIP, relationship, whether the dependency was `present_at_creation`, `introduced`, `changed`, or `removed`, the associated commit and date, and its source IDs. Use `other` with an explanation if the relationship does not fit `requires`, `extends`, `interacts_with`, `replaces`, or `supersedes`.

## Evidence hierarchy

Prefer primary sources in this order:

1. the authoritative fork-membership document given in the fork input;
2. Git history and pull requests in `ethereum/EIPs`;
3. contemporaneous AllCoreDevs agendas, minutes, recordings, and decision issues in `ethereum/pm`; and
4. pinned execution-specs or consensus-specs documents referenced by the authoritative source.

Secondary summaries may be used only as discovery aids. Every reported date, status transition, membership decision, revision, and dependency event must reference at least one source ID or be explicitly marked `unknown`.

Each work unit owns a source registry shaped like `templates/source-registry-output.yaml`. Every individual observation references entries in that registry through `source_ids`.

Use these source types where applicable: `git_commit`, `git_blob`, `github_pull_request`, `github_issue`, `meeting_minutes`, `meeting_recording`, `web_page`, or `other`. Use `snapshot_policy: reproducible_from_git`, `archived`, or `reference_only`. Record redistribution status as `allowed`, `restricted`, `unknown`, or `not_applicable`.

For Git sources, record the repository, full commit SHA, path, and immutable GitHub permalink. These fields are sufficient to reproduce Git content and diffs; a duplicate raw snapshot is optional.

Mutable sources—including GitHub issue and pull-request metadata, HackMD pages, and non-versioned web pages—must be captured under the work unit's `raw/` directory. Record the canonical URL, retrieval timestamp, archive path, content hash, and redistribution status. If redistribution is not permitted or is unclear, retain a reproducible reference and metadata without copying the protected content, and use `snapshot_policy: reference_only`.

Recordings and other impractical binary sources may remain reference-only, but the source entry must include the relevant timecode or locator in its notes.

## Procedure

### Fork work unit

1. Read the fork input and resolve source revisions.
2. Extract the fork membership inventory using only the configured source sections and rules.
3. Classify affected layers and record the evidence for the classification.
4. Reconstruct inclusion-state events from Meta EIP history and contemporaneous AllCoreDevs evidence.
5. Register every source, archive mutable evidence where permitted, and attach source IDs to each observation.
6. Write the fork record, source registry, and one fork–EIP relationship record per inventoried EIP.
7. Verify that inventory counts derive from the relationship records and that every factual date has evidence.

### EIP work unit

1. Confirm that the EIP occurs in at least one reviewed fork inventory.
2. Record its frontmatter creation date and earliest repository commit.
3. Inspect its complete EIPs-repository history and classify every file-changing commit.
4. Extract explicit cross-EIP dependency events without inferring unstated relationships.
5. Derive revision counts and first/last dates from the event list; never enter aggregates independently.
6. Register every source and attach source IDs to each observation.
7. Write the single global EIP-history record and its source registry.
8. Verify that every source ID resolves, every Git event has an immutable permalink, and every uncertain classification has an explanation.

## Outputs

Write only under the path owned by the assigned work unit:

```text
outputs/
├── forks/
│   └── <fork-id>.yaml
├── fork-eips/
│   └── <fork-id>/
│       └── eip-<number>.yaml
├── eips/
│   └── eip-<number>.yaml
├── sources/
│   ├── forks/
│   │   └── <fork-id>.yaml
│   └── eips/
│       └── eip-<number>.yaml
└── manifests/
    └── eip-work-units.yaml

raw/
├── forks/
│   └── <fork-id>/
│       └── <source-id>.<ext>
└── eips/
    └── eip-<number>/
        └── <source-id>.<ext>
```

Use:

- `templates/fork-output.yaml` for `outputs/forks/<fork-id>.yaml`;
- `templates/fork-eip-output.yaml` for fork–EIP relationship records;
- `templates/eip-output.yaml` for global EIP histories;
- `templates/source-registry-output.yaml` for per-work-unit source registries; and
- `templates/eip-work-units-output.yaml` for the coordinator-owned deduplicated assignment manifest.

Concurrent workers must never write the same file. Fork agents own their fork record, fork–EIP directory, source registry, and raw directory. EIP agents own one global EIP record, source registry, and raw directory. Only the coordinator writes the assignment manifest.

## Acceptance criteria

### Fork output

- The inventory accounts for every EIP selected by the input and no out-of-scope EIP.
- Each fork–EIP relationship has explicit `layers`, membership classification, and evidence.
- Historical source terminology is retained alongside any normalized inclusion state.
- Every inclusion-state cycle found in primary sources is preserved; derived counts match the event list.
- Every moving source is pinned to a commit.

### EIP output

- Each unique EIP has exactly one global history record.
- Frontmatter and repository creation dates are both recorded and discrepancies remain visible.
- Every EIP-file commit has been reviewed.
- Substantive, non-substantive, and uncertain revisions are distinguishable.
- Revision counts and first/last dates are mechanically derivable from the event list.
- Every explicit cross-EIP dependency event has a target, relationship, date or explicit unknown, and primary-source evidence.

### All output

- Every factual date has primary-source evidence through a resolvable source ID.
- Every mutable source is archived with a content hash when redistribution permits, or explicitly marked reference-only.
- Source IDs are unique and every referenced source ID exists in the owning work unit's registry.
- Unknowns and negative searches remain visible rather than being filled by inference.
- No client, devnet, assessment-date, complexity-score, or observed-complexity result is produced.
