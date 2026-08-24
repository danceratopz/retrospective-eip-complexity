# Task 02: Reconstruct client implementation history

## Objective

For one execution-layer EIP, identify the earliest traceable substantive implementation work in each configured execution client and determine when implementation was underway in at least two independent clients.

This task gathers implementation evidence. It does not reconstruct the EIP text, infer fork membership, score complexity, choose an assessment date, or measure devnet participation.

## Inputs

Each run receives one YAML file shaped like `templates/input.yaml`. The input must identify exactly one EIP, point to its reviewed Task 01 record or records, and reference the approved client cohort. Multiple Task 01 records are expected when the same EIP appears in more than one fork.

Only run this task when the reviewed Task 01 record has `execution` in `eip.layers`. Run it once per unique EIP, even when that EIP appears in more than one fork.

The approved cohort is stored once in `inputs/client-cohort.yaml`; do not copy or silently narrow it in per-EIP inputs. Every client repository must be a complete clone with all relevant refs and history. A default-branch-only or shallow clone is insufficient. GitHub issue and pull-request metadata must be queried separately because it is not present in Git history.

A client that did not yet exist during the EIP's original development may still contain later implementation evidence. Preserve that evidence, but flag it as post-fork context rather than treating it as evidence about the original fork-development period.

## Definitions

### Qualifying implementation work

A candidate qualifies when it contains implementation code or tests that exercise EIP-specific behavior. Partial work qualifies if it implements a material part of the proposal and is more than scaffolding.

The following do not qualify by themselves:

- an issue, roadmap item, or statement of intent;
- an EIP-number constant, fork-name placeholder, or empty feature flag;
- release notes or documentation;
- dependency updates without EIP-specific behavior;
- code review comments without an implementation diff.

Preserve borderline and rejected candidates in the output with a rationale. Do not silently discard them.

### First traceable work per client

For every qualifying candidate, record all available timestamps rather than collapsing them:

- commit author time;
- commit committer time;
- pull-request creation time;
- pull-request merge time; and
- release time, if it materially helps interpret the record.

Set `first_qualifying_work` to the earliest qualifying candidate supported by the searched public history. Record an `evidence_date`, the date-selection rule used, and a confidence level. These timestamps identify the earliest work recoverable from public evidence; they do not prove when private development began or when a branch was first pushed.

### Development underway in earnest

For this study, development was underway in earnest once a second independent cohort client had qualifying implementation work.

Sort the clients' `first_qualifying_work.evidence_date` values and select the second. Record the two qualifying clients and source event IDs. If fewer than two clients qualify, set `reached: false` and leave the date null.

This is a derived research heuristic, not a claim about the exact historical start of development.

## Sources and provenance

Use primary sources:

1. commits and all relevant refs in the client repository;
2. GitHub pull requests, reviews, issues, and event metadata;
3. client release notes only as corroborating evidence; and
4. contemporaneous AllCoreDevs or implementers-call records only as corroborating evidence.

Use immutable GitHub commit permalinks for commits. Record repository, full commit SHA, and relevant paths. For mutable pages such as issues and pull requests, record the canonical URL, retrieval time, and the exact metadata used.

Search by more than the EIP number. Use proposal terminology, opcode or precompile identifiers, configuration names, linked PRs, authors, and known dependency EIPs. Record searches that produce no result.

## Procedure

1. Validate that the input EIP affects the execution layer and that every cohort repository is complete enough to search.
2. Read the historical EIP record or records so searches use names and terminology that existed at the time.
3. Search all refs and GitHub metadata in every cohort client.
4. Record candidate implementation events, including rejected and ambiguous candidates.
5. Select the first qualifying work per client and explain the choice.
6. Derive the two-client threshold only from the selected per-client events.
7. Write one output file using `templates/output.yaml`.
8. Verify that all dates, commits, paths, pull requests, and negative search results have provenance.

## Outputs

Write one file under `outputs/`:

```text
outputs/eip-<number>.yaml
```

Do not group results by fork. Fork membership is a many-to-many relationship supplied by Task 01; client implementation history belongs to the EIP.

## Acceptance criteria

- The input points to at least one reviewed execution-affecting EIP record, with every known fork occurrence listed.
- Every cohort client has a completed search record, including explicit negative results or a documented reason the repository could not be searched.
- Every qualifying, rejected, and ambiguous candidate has a concise rationale and primary-source evidence.
- The selected first work in each client is consistent with the recorded candidates.
- Author, committer, PR creation, and PR merge times remain distinct.
- `development_in_earnest` is mechanically derivable from the selected per-client evidence dates.
- The result does not claim to know when private or unpublished work began.
- No complexity score, assessment date, devnet history, or observed-complexity judgment is produced.
