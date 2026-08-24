# Task 04: Select complexity-assessment EIP refs

## Objective

For every execution-affecting EIP in one fork, select the exact historical `ethereum/EIPs` revision that a later retrospective complexity assignment must evaluate. Include cross-layer EIPs; exclude consensus-only EIPs while the study assesses execution-layer complexity only.

The selected revision should represent the EIP at Proposed for Inclusion (PFI), or at the closest defensible historical equivalent for forks that predate explicit PFI terminology. The default is the latest EIP-file revision at or before the verified proposal anchor. A revision shortly after the anchor may be proposed only as a documented exception.

This task selects refs. It does not reconstruct supporting design material, identify development-start dates, inspect client implementations or devnets, score complexity, or approve the final complexity assignment.

## Input

Each fork run receives one required `fork_id` in its wrapper prompt.

The fork must already have reviewed Task 01 records under:

```text
research/tasks/01-fork-eip-history/outputs/
├── forks/<fork-id>.yaml
├── fork-eips/<fork-id>/eip-<number>.yaml
├── eips/eip-<number>.yaml
└── sources/
```

Task 01 is authoritative for fork membership, inclusion-state events, EIP creation, and classified EIP-file revisions. Do not silently correct or reinterpret Task 01. If a material error is discovered, record it as an unknown and report it to the coordinator for a separate Task 01 correction.

## Work units

### Fork coordinator

The coordinator receives one `fork_id`, enumerates the Task 01 fork–EIP records for that fork, filters them to records whose `eip.layers` contains `execution`, and assigns exactly one work unit per remaining EIP. One agent per EIP is the preferred boundary because each worker makes one independently reviewable historical-ref decision and owns one output file.

Workers may run concurrently in waves. They must never write the same file. Only the coordinator checks fork completeness and cross-EIP consistency.

### EIP worker

Each worker receives exactly:

- `fork_id`;
- `eip_number`; and
- the path to this task contract.

The worker writes only:

```text
outputs/fork-eips/<fork-id>/eip-<number>.yaml
```

Use `templates/output.yaml`. Do not modify Task 01 records, task contracts, templates, prompts, or another EIP's output.

## Definitions

### Proposal anchor

The proposal anchor is the event against which EIP-file revisions are bracketed.

Use one of these `anchor.kind` values:

- `explicit_pfi`: the authoritative fork document explicitly placed the EIP in PFI;
- `normalized_proposal_equivalent`: Task 01 identified a contemporaneous proposal event that predates or does not use literal PFI terminology;
- `fallback_cfi`: no credible proposal event exists, so the earliest CFI-equivalent event is used and the limitation is explicit; or
- `other`: another defensible anchor is necessary and fully explained.

For explicit PFI under the EIP-7723 process, PFI is set when the change adding the EIP to the Meta EIP's PFI section is merged. A pull-request opening time may be useful context but is not itself the PFI-set time.

Record both:

- `effective_at`: when the proposal state actually took effect; and
- `recorded_at`: when the source repository recorded the state, if different.

For a direct Meta EIP merge these are normally the same. For an older meeting decision recorded later in Git, they may differ. Preserve Task 01's raw historical label and source IDs.

If multiple proposal cycles exist, select the proposal event belonging to the inclusion cycle that ultimately produced the fork's included EIP. Preserve earlier or competing event IDs under `alternative_event_ids` and explain the selection. Do not hide a removal and later re-proposal.

### Bracketing revisions

The preceding candidate is the latest Task 01 creation or revision event whose UTC commit time is at or before `anchor.effective_at`.

The following candidate is the earliest Task 01 revision event after `anchor.effective_at`.

Record both when they exist, even when the choice is obvious. Derive signed `offset_from_anchor_seconds` mechanically:

- negative: before the anchor;
- zero: exactly at the anchor; and
- positive: after the anchor.

Do not use author time, frontmatter `created`, pull-request creation time, or a commit date truncated to a calendar day when an exact committer timestamp exists.

### Selected assessment ref

The default selection is the preceding candidate. `selection.mode` is `preceding`.

The selected revision records the exact repository, full commit SHA, path, committer time, Git blob SHA, content SHA-256, immutable GitHub blob URL, and Task 01 source IDs. These fields identify the exact specification content later complexity work must read.

`information_cutoff_at` is the latest contemporaneous evidence time permitted to the later reconstruction task:

- normally the verified proposal anchor time when the preceding revision is selected; or
- the selected revision's commit time when a post-anchor exception is selected.

This distinction allows an older unchanged EIP ref to be read with context available at PFI without allowing later development history into the assessment.

### Post-anchor exception

Use `selection.mode: post_anchor_exception` only when all of the following hold:

1. the following revision is no more than seven calendar days after the anchor;
2. its diff against the preceding candidate was reviewed directly;
3. it plausibly completes or corrects the proposal being submitted at PFI;
4. it does not incorporate CFI, SFI, devnet, client-implementation, testing, or later design feedback; and
5. the output records the diff's semantic effect, a concise justification, and hindsight risk.

Seven days is an eligibility ceiling, not an automatic nearest-commit rule. Prefer the preceding candidate when the following commit is merely closer in absolute time. A worker may propose a post-anchor exception but must set `review.status: needs_human_review`; it may not self-approve the exception.

If no preceding candidate exists because the EIP file was created after the proposal anchor, select the creation revision as `post_anchor_exception`, explain the chronology, and require human review.

## Procedure

### Fork coordinator

1. Read the fork wrapper and this task completely.
2. Verify that the Task 01 fork record and fork–EIP directory exist.
3. Enumerate EIPs only from `outputs/fork-eips/<fork-id>/`; retain execution-only and cross-layer records, exclude consensus-only records, and do not reconstruct membership.
4. Dispatch one EIP work unit per EIP, in waves if concurrency is limited.
5. Ensure each EIP has exactly one output and no worker changed an out-of-scope path.
6. Check that selected commits, paths, URLs, hashes, offsets, and information cutoffs are internally consistent.
7. Summarize preceding selections, proposed post-anchor exceptions, fallbacks, and records needing human review.

### EIP worker

1. Read this task, the assigned fork–EIP record, the global EIP-history record, and their referenced source registries.
2. Enumerate all proposal-for-inclusion events in the fork–EIP record.
3. Verify the selected anchor from its primary evidence, especially the exact time PFI was set.
4. Select and justify the anchor; preserve alternative proposal-cycle event IDs.
5. Normalize all relevant commit times to UTC and mechanically identify the preceding and following EIP-file revisions.
6. Apply the default preceding rule. Consider a post-anchor exception only under the complete exception test above.
7. Resolve the selected Git blob, calculate its SHA-256, and construct an immutable GitHub blob URL.
8. Write the single output from `templates/output.yaml`.
9. Re-read the result and confirm that every factual field is derived from the cited Task 01 records or immutable Git content.

## Output

```text
outputs/
└── fork-eips/
    └── <fork-id>/
        └── eip-<number>.yaml
```

Records are fork-specific because proposal state belongs to the relationship between an EIP and a fork. The same EIP may legitimately receive different assessment refs in different forks.

All worker outputs remain proposals until human review. Later complexity-assessment tasks must consume only records with `review.status: approved`.

## Acceptance criteria

- The fork ID and EIP number match the referenced Task 01 records.
- One output exists for every execution-affecting Task 01 fork–EIP record, consensus-only EIPs have no output, and no extra EIP is added.
- The proposal anchor preserves the historical raw label and distinguishes explicit PFI, normalized equivalents, and fallbacks.
- The exact PFI/equivalent effective time is verified from primary evidence rather than inferred from a later state.
- Multiple proposal cycles remain visible.
- Preceding and following candidates are mechanically derived from the complete Task 01 EIP history.
- The preceding candidate is selected by default.
- Every post-anchor exception satisfies the seven-day ceiling, includes a direct diff review, explains hindsight risk, and requires human review.
- The selected ref includes a full commit, path, timestamp, Git blob SHA, content SHA-256, immutable link, and rationale.
- `information_cutoff_at` follows the selected mode.
- Unknowns and ambiguities remain explicit.
- No complexity score, historical supporting-material package, client history, devnet history, development-start estimate, or observed-complexity judgment is produced.
