# Reproducing the workflow

## Reproducibility boundary

This workflow has three kinds of operations:

1. **Evidence reconstruction** is agent-assisted and interpretive. It is repeatable through task contracts, immutable sources, raw captures, and explicit uncertainty, but independent researchers may disagree on classifications.
2. **Transformation and rendering** are deterministic. Unchanged inputs, scripts, and locked dependencies should produce identical outputs.
3. **Human review** is a recorded decision gate. Reproducibility means the evidence, proposed value, reviewer, rationale, and final value are all recoverable; it does not mean every reviewer must reach the same judgment.

## Prerequisites

Install Git and [uv](https://docs.astral.sh/uv/). The locked Task 03 and Task 05 projects support Python 3.11 through 3.13; `uv` creates and manages their environments.

For operations that resolve historical Git blobs, place complete upstream clones next to this repository or provide the explicit path accepted by the relevant script:

```text
github/
├── retrospective-complexity-eval/
├── EIPs/                 # ethereum/EIPs
├── pm/                   # ethspecs/pm, for the pinned complexity rubric
├── consensus-specs/      # ethereum/consensus-specs
└── execution-specs/      # ethereum/execution-specs, needed by older-fork research
```

Do not use shallow clones for historical reconstruction. The exact upstream commits are recorded in Task 01 fork records, source registries, Task 03 source registries, and Task 05 manifests. Do not replace those pins with current default branches.

The timeline renderer may install locked packages from PyPI on its first run. Task 05 assessor sessions themselves are prohibited from using the internet and must run only through the isolated launcher.

## Task 01: fork membership and EIP histories

Read `research/tasks/01-fork-eip-history/TASK.md` completely.

Task 01 has two agent work-unit types:

- one fork work unit per fork, using `inputs/<fork>.yaml` and `prompts/<fork>.md`; and
- one global work unit per unique EIP, using `prompts/eip.md` after the fork inventories have been reviewed and deduplicated.

Fork workers own only their fork record, fork–EIP directory, source registry, and raw evidence directory. EIP workers own only one global EIP history and its source registry/raw directory. The coordinator alone writes the deduplicated EIP work-unit manifest.

Task 01 is complete for the five configured forks. Reproduction should verify every source ID, Git event, aggregate, and raw snapshot against the task acceptance criteria rather than silently rewriting reviewed data.

## Task 02: client implementation history

Read `research/tasks/02-client-implementation-history/TASK.md` completely.

Task 02 runs once per unique execution-affecting EIP against the cohort in `inputs/client-cohort.yaml`. It records the earliest qualifying implementation or test work in each client and mechanically identifies the second independent client as the study's “development underway in earnest” heuristic.

This task is independent of Task 03/04 ref selection and is not yet populated in the initial snapshot.

## Task 03: development timelines

Read `research/tasks/03-fork-development-timelines/TASK.md` completely. Task 03 joins reviewed Task 01 data with fork milestones, devnet launches, and evidence-backed per-EIP devnet participation.

From the repository root:

```bash
uv sync --project research/tasks/03-fork-development-timelines --locked
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/03-fork-development-timelines/scripts/render.py --validate-only
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/03-fork-development-timelines/scripts/render.py
```

Only Amsterdam and Osaka are currently configured. Add Shanghai, Cancun, and Prague by creating one `inputs/forks/<fork>.yaml` and one `inputs/sources/<fork>.yaml` under the Task 03 contract, then validate the individual fork before rendering.

Each configured fork emits a fork overview, EL histories, and CL histories as offline HTML, SVG, PDF, and Vega-Lite JSON, plus normalized `plot-data.json` and `plot-manifest.yaml`.

## Task 04: historical assessment refs

Read `research/tasks/04-complexity-assessment-ref-selection/TASK.md` completely, then use the wrapper in `prompts/<fork>.md`.

The coordinator enumerates execution-affecting Task 01 fork–EIP records, including cross-layer EIPs and excluding consensus-only EIPs. One worker per EIP is the preferred boundary. Each worker writes only:

```text
research/tasks/04-complexity-assessment-ref-selection/outputs/fork-eips/<fork>/eip-<number>.yaml
```

The default assessment ref is the latest EIP-file revision at or before the verified PFI or historical proposal-equivalent anchor. A post-anchor revision is eligible only under the complete seven-day exception test in the contract. Under-specification is evidence and is not a reason to move to a later polished revision.

After coordinator verification, render the proposed refs over the Task 03 EL timeline:

```bash
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04-complexity-assessment-ref-selection/scripts/render_review.py --validate-only --fork osaka
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04-complexity-assessment-ref-selection/scripts/render_review.py --fork osaka
```

Replace `osaka` with another configured fork after its Task 03 inputs and Task 04 records exist. The resulting interactive artifact is under `research/tasks/04-complexity-assessment-ref-selection/outputs/review/<fork>/`.

The current review renderer checks inventory, selected-commit presence and timestamp, and anchor-event presence and timestamp. Until a complete Task 04 validator is implemented, the coordinator must additionally recompute revision brackets, signed offsets, Git blob hashes, content hashes, immutable URLs, source IDs, information cutoffs, exception eligibility, and review-state consistency.

All records remain proposals until a human reviews the timeline and underlying evidence. Only records with `review.status: approved` may be consumed by Task 05. Preserve the original proposal in a fork run log if human review changes the selected ref.

## Task 05: isolated complexity assignment

Read `research/tasks/05-retrospective-complexity-assignment/TASK.md` and its `README.md` completely.

Task 05 consumes an approved Task 04 ref and packages exactly the permitted historical EIP text, pinned rubric, and allowlisted contemporaneous supporting material. One fresh `gpt-5.6-sol` session at `xhigh` assesses one EIP. The assessor sees only the sealed capsule, cannot access the network, repository, vault, other EIPs, or prior assessments, and writes only `assessment.yaml`.

Rebuild and validate deterministic packages from the repository root:

```bash
uv run --project research/tasks/05-retrospective-complexity-assignment --locked python research/tasks/05-retrospective-complexity-assignment/scripts/prepare_inputs.py --fork osaka
uv run --project research/tasks/05-retrospective-complexity-assignment --locked python research/tasks/05-retrospective-complexity-assignment/scripts/validate_inputs.py --fork osaka
```

Preview or run pending isolated sessions from the Task 05 directory:

```bash
cd research/tasks/05-retrospective-complexity-assignment
uv run --locked python scripts/run_fork.py --fork osaka --jobs 3 --dry-run
uv run --locked python scripts/run_fork.py --fork osaka --jobs 3
```

The initial Osaka assignments are already complete. The orchestrator skips canonical outputs that already exist. Do not delete or overwrite an original assessment to force a rerun; independent verification belongs to Task 06 and must preserve the original score.

Task 05 currently records completion in a Danos vault checklist through a machine-local path in `config.yaml`. This integration is optional for data validation but required by the current launcher completion step; make it configurable before running on another machine.

## Deterministic rerender check

For a configured fork, hash the output directory, rerender from unchanged inputs, and require an empty diff. For example:

```bash
find research/tasks/03-fork-development-timelines/outputs/osaka -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/osaka-before.sha256
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/03-fork-development-timelines/scripts/render.py --fork osaka
find research/tasks/03-fork-development-timelines/outputs/osaka -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/osaka-after.sha256
diff -u /tmp/osaka-before.sha256 /tmp/osaka-after.sha256
```

Repeat the same procedure for `research/tasks/04-complexity-assessment-ref-selection/outputs/review/<fork>` after running `render_review.py`.

## Viewing offline plots

Open an HTML file directly, or serve an output directory on a trusted local network:

```bash
python3 -m http.server 8000 --bind 0.0.0.0 --directory research/tasks/04-complexity-assessment-ref-selection/outputs/review/osaka
```

Use `hostname -I` to identify the machine's LAN address and stop the server with Ctrl-C. Do not expose the server to an untrusted network.

## Known reproducibility gaps

- Task 03 source reconstruction remains to be completed for Shanghai, Cancun, and Prague.
- Task 04 ref selection is agent-coordinated and lacks a complete executable validator and run manifest.
- The Task 04 vocabulary and policy for direct-SFI fallbacks, decision time versus later Meta EIP recording time, and pre-merge proposal refs are not yet frozen in schema.
- Human review decisions do not yet have a dedicated structured decision file.
- Task 05 launcher paths for Codex and the Danos checklist are machine-specific.
- Task 06 independent verification is not yet defined.

These gaps should be resolved before claiming that a clean checkout can reproduce the complete study without local operator knowledge.

