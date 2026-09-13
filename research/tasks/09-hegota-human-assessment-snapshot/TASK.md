# Task 09: Hegotá human-assessment snapshot

## Objective

Record, without scoring anything, which Hegotá candidate EIPs have a STEEL human
complexity checklist in the `ethspecs/pm` repository, where each checklist
lives, and how complete it is. The publication site uses this record to show the
human assessment source for Hegotá alongside the frozen Task 08 LLM assessments
and to state honestly which human assessments do not yet exist.

Merged files on the upstream default branch do not represent the complete
Hegotá state: most checklists are still in open pull requests, several are
drafts, and a few are internally inconsistent. This task captures all of those
states explicitly instead of collapsing them into "present" or "absent".

## Population

The population is the 46-entry Task 08 combined view
`hegota-candidates-2026-08-26-ac450a4` (44 PFI, EIP-7805 SFI, EIP-8141 CFI). It
is read from
`research/tasks/08-hegota-prospective-complexity-assessment/outputs/summary-all-candidates.yaml`
and hashed into the capture manifest. Checklists for EIPs outside that
population are ignored.

## Sources

- `ethspecs/pm` default branch (`main`), directory `complexity_assessments/EIPs/`.
- Every open pull request in `ethspecs/pm` that adds or modifies a checklist in
  that directory, including draft pull requests and pull requests from forks.
- `ethspecs/pm` is licensed CC0-1.0, so checklist bodies are archived verbatim
  under `raw/<snapshot-id>/` with blob and content hashes.

Amsterdam human checklists are owned by Task 05c and are not re-captured here.

## Independence

Task 08 assessors never read this task. This task never reads Task 08 scores
beyond the population list, and it never modifies a Task 08 record. It also
never invents a score: a blank checklist cell is interpreted as zero only when
the checklist's own published total proves that interpretation, following the
Task 05c convention.

## Method

```bash
TASK=research/tasks/09-hegota-human-assessment-snapshot
uv run --project research/tasks/05-retrospective-complexity-assignment --locked \
  python $TASK/scripts/snapshot_pm_assessments.py capture
uv run --project research/tasks/05-retrospective-complexity-assignment --locked \
  python $TASK/scripts/snapshot_pm_assessments.py parse --snapshot-id <snapshot-id>
```

`capture` needs network access and an authenticated `gh` CLI. It writes only
`raw/<snapshot-id>/`. `parse` is offline and deterministic: it reads the archived
bodies and the capture manifest, verifies their hashes, and writes `outputs/`.

Checklist parsing recognises checklist revision 1 (24 criteria, nominal maximum
72, tiers `<10`, `10–19`, `≥20`) and revision 2 (28 criteria, nominal maximum 84,
tiers `<12`, `12–22`, `≥23`) by the declared revision line and the exact row
inventory. Score cells must be additive integers. Published totals, the Final
Assessment total, and the tier symbol are recorded as written; a recomputed total
and tier are recorded separately.

## Status vocabulary

Each EIP receives exactly one `human_assessment_status`, chosen from the smallest
set that the real sources distinguish. Candidates are ranked complete before
incomplete, newer checklist revision before older, then merged before open pull
request before draft pull request. A pull-request checklist whose score cells and
total equal the merged checklist is recorded as `duplicates_merged_scores` and
does not count as a distinct source.

| Status | Meaning |
| --- | --- |
| `complete` | A complete checklist is merged on the default branch. |
| `available_in_open_pr` | A complete checklist exists only in an open, non-draft pull request. |
| `in_progress` | The most advanced checklist is in an open draft pull request. |
| `incomplete` | A checklist exists but has unresolved cells, missing rows, or inconsistent totals. |
| `not_yet_available` | No checklist exists on the default branch or in any open pull request. |

None of these states is a score. A consensus-only Task 08 disposition remains
`not_applicable_to_el_rubric` for the LLM source regardless of this status.

## Outputs

```text
raw/<snapshot-id>/capture-manifest.yaml   # upstream head, population hash, pull-request inventory
raw/<snapshot-id>/main/EIP-NNNN.md        # archived default-branch checklists
raw/<snapshot-id>/pr-NNN/EIP-NNNN.md      # archived pull-request checklists
outputs/snapshot.yaml                     # status vocabulary, counts, per-EIP status, pull requests
outputs/assessments/eip-NNNN.yaml         # every parsed candidate checklist for one EIP
```

`outputs/` is canonical for this task. Re-running `parse` on the same snapshot
must reproduce it byte-for-byte. A new capture creates a new snapshot identifier
and must be reviewed before the publication adapter is pointed at it.

## Current state

- Snapshot `hegota-human-2026-09-13-3d8c012`: upstream head
  `3d8c0128c5543dd3146341ef395aa344e4abea30`, 4 default-branch checklists, 24
  open pull requests touching population checklists.
- Status counts: 2 complete, 14 available in open pull requests, 8 in progress,
  1 incomplete, 21 not yet available (7 of the 21 are Task 08 not-applicable
  dispositions).
