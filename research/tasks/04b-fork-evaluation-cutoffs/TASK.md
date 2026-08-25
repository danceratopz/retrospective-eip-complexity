# Task 04b: Define fork evaluation cutoffs

## Objective

For each fork, freeze the historical cutoff that separates final execution-affecting EIPs which were already in the initial scope-setting horizon from EIPs added later. This preserves two distinct questions:

1. What complexity could the original fork-scoping process have forecast?
2. How complex was the complete scope that ultimately shipped or is currently scheduled?

Task 04b controls fork-level aggregation only. It does not change an EIP's approved Task 04 assessment ref, omit late EIPs from individual assessment, redistribute a late EIP's score into another EIP, or assign complexity.

## Inputs

- reviewed Task 01 fork membership, inclusion histories, and provenance registries;
- Task 03 fork timelines for visual review;
- human-approved Task 04 historical assessment refs; and
- contemporaneous primary evidence for the relevant scope-setting decision.

## Definitions

### Fork evaluation cutoff

The cutoff is the final initial scope-setting decision before the fork's main implementation cycle. Prefer an explicit scope freeze. For older forks without that term, use the decision that froze the initial included or scheduled set before broad devnet implementation. A later inventory close to mainnet is not an acceptable substitute.

Record separately:

- `effective_at`: the historical decision date or instant;
- `recorded_at`: the time the resulting state was recorded in an authoritative repository, when different; and
- `precision`: `day` or `instant`.

The cutoff is a fork-level aggregation horizon. It is not an information boundary for an individual EIP assessment; Task 04's `selection.information_cutoff_at` remains authoritative for that purpose.

### Forecastable cohort

A final execution-affecting EIP belongs to `forecastable_at_cutoff` when it had entered the fork's credible proposal, consideration, or scheduling set by the cutoff. An event that records the cutoff decision shortly afterward may be used only with `timing_relation: cutoff_decision_recorded_after` and an explicit rationale.

### Late-scope cohort

A final execution-affecting EIP belongs to `late_scope` when its first credible fork-scope event occurred after the cutoff, or when it was known but explicitly remained outside the frozen scope until a later addition.

Classify late scope as one of:

- `derived_companion`: introduced to complete, constrain, or repair another scoped feature;
- `independent_addition`: a later feature addition without an evidenced dependency on initial scope;
- `ancillary_or_non_consensus`: later supporting, informational, networking, or API scope;
- `optional`: not required at fork activation; or
- `unresolved`: the relationship is not established.

Causal attribution is analytical metadata, not a score transfer. Use `evidence_backed` only with cited contemporaneous or specification evidence. Use `project_owner_hypothesis` or `research_hypothesis` when the relationship is a hypothesis that later work must test.

## Aggregation policy

Every final execution-affecting EIP is assessed individually at its approved Task 04 ref. Later fork reports calculate three views from the unchanged original EIP scores:

- `initial_forecast_total`: sum only `forecastable_at_cutoff` EIPs;
- `final_scope_total`: sum every final execution-affecting EIP; and
- `late_scope_increment`: sum only `late_scope` EIPs.

The initial forecast is the primary retrospective comparison. The final total describes delivered scope. The increment measures the forecast gap. Never silently fold a late companion's score into its proposed parent; preserve both original scores and analyze the relationship separately.

## Procedure

1. Enumerate the complete execution-affecting inventory from approved Task 04 records.
2. Identify the strongest contemporaneous initial scope-freeze or equivalent decision.
3. Record the effective and repository-recording times with source IDs.
4. For every final EIP, resolve one Task 01 scope-basis event and classify it into exactly one cohort.
5. Record a late-scope type and cautious attribution only for late EIPs.
6. Validate inventory, event IDs, timestamps, sources, review state, and counts mechanically.
7. Render the cutoff over the approved Task 04 EL review timeline.
8. Present the proposed cutoff, cohorts, late additions, and ambiguities for human review.
9. Change `review.status` to `approved` only after an explicit human decision.

## Output

```text
outputs/
├── aggregation-policy.yaml
├── forks/
│   └── <fork>.yaml
└── review/
    └── <fork>/
        ├── el-evaluation-cutoff-review.html
        ├── el-evaluation-cutoff-review.svg
        ├── el-evaluation-cutoff-review.pdf
        ├── el-evaluation-cutoff-review.vl.json
        ├── plot-data.json
        └── plot-manifest.yaml
```

## Acceptance criteria

- Every and only approved Task 04 execution-affecting EIP appears once.
- Cohorts are disjoint and complete.
- Every scope-basis event resolves to the matching Task 01 fork–EIP record.
- Timing relations are mechanically consistent with `effective_at` and `recorded_at`.
- Every cutoff source ID resolves through the declared Task 01 source registry.
- Late attribution is explicitly evidential, hypothetical, or absent.
- Aggregation preserves original EIP scores and reports initial, final, and increment views separately.
- The review timeline displays the same cutoff in every EL EIP panel and labels each EIP's cohort.
- Proposed records are not self-approved.
