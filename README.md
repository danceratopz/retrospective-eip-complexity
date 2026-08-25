# Retrospective EIP complexity evaluation

This repository applies the current EIP complexity rubric retrospectively to execution-affecting EIPs from recent Ethereum hard forks. Each EIP is assessed using a historical specification revision intended to approximate what reviewers knew when the proposal entered fork development, rather than the final specification that eventually shipped.

The study is designed to answer two questions:

1. Do the current complexity criteria produce sensible results for EIPs whose development histories are already known?
2. Do the criteria, their wording, or their weighting need calibration before prospective use?

The initial fork range is Shanghai/Shapella through Amsterdam/Glamsterdam. Execution-only and cross-layer EIPs are assessed; consensus-only EIPs remain in the historical dataset and plots but are not assigned execution-layer complexity scores.

## Start here

- [REPRODUCING.md](REPRODUCING.md) describes the end-to-end research and review process.
- [DATA.md](DATA.md) explains what is canonical, derived, generated, or deliberately excluded.
- [research/README.md](research/README.md) describes the task-oriented directory structure.
- Every task has its own `TASK.md` contract, inputs, templates, outputs, and provenance rules.

## Workflow

```text
Task 01: fork membership and EIP histories
    |
    +--> Task 02: client implementation history
    |
    +--> Task 03: fork, EL, and CL development timelines
              |
              +--> Task 04: assessment-ref selection and human review
                         |
                         +--> Task 04b: fork evaluation cutoffs and aggregation cohorts
                         |
                         +--> Task 05: isolated historical complexity assignment
                                    |
                                    +--> Task 06: independent verification (planned)
```

Task 02 is independent supporting research and is not required to choose the Task 04 historical assessment ref. Tasks 03 and 04 provide the timeline-based human review used to freeze that ref. Task 04b separately defines which final EIPs were forecastable at the initial fork-scoping horizon; it never changes an EIP's assessment ref or score. Task 05 consumes only approved Task 04 records and then seals each EIP into a hindsight-controlled, one-EIP assessment package.

## Current state

| Task | State |
| --- | --- |
| Task 01 | Complete for Shanghai, Cancun, Prague, Osaka, and Amsterdam |
| Task 02 | Contract and client cohort prepared; implementation research not yet run |
| Task 03 | All five fork timelines rendered and validated |
| Task 04 | All 49 execution-affecting fork–EIP refs selected, human-approved, and mechanically validated |
| Task 04b | Cutoffs and initial/late aggregation cohorts proposed for all five forks; human review pending |
| Task 05 | Twelve Osaka assessments completed and mechanically validated |
| Task 06 | Not yet defined |

## Reproducibility model

The deterministic parts of the workflow—data joins, sealed package construction, validation, and rendering—are expected to reproduce byte-for-byte from unchanged inputs and locked dependencies.

Historical interpretation and human review cannot be guaranteed to produce identical prose or decisions. They must instead be independently auditable: every observation carries source provenance, every selected ref identifies an exact Git blob, uncertainty remains explicit, and human decisions are retained rather than silently overwritten.

## Repository status

This repository was created as a local research checkpoint. No remote is configured and nothing has been published. A license and a publication review of raw evidence and operational metadata are still required before public distribution.
