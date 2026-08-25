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

All five forks are configured. Each emits a fork overview, EL histories, and CL histories as offline HTML, SVG, PDF, and Vega-Lite JSON, plus normalized `plot-data.json` and `plot-manifest.yaml`.

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

The Task 04 validator checks inventories, anchor-policy precedence, UTC brackets, signed offsets, selected commits, Git blob and content hashes, immutable URLs, exception gates, information cutoffs, review state, and cross-fork reuse:

```bash
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04-complexity-assessment-ref-selection/scripts/validate_outputs.py
```

All 49 configured records are human-approved. Only records with `review.status: approved` may be consumed by Task 05. Preserve the original proposal in a fork run log if human review changes the selected ref.

## Task 04b: fork evaluation cutoffs

Read `research/tasks/04b-fork-evaluation-cutoffs/TASK.md` completely. Task 04b defines a fork-level initial evaluation horizon separately from each EIP's Task 04 information cutoff. It partitions final execution-affecting EIPs into `forecastable_at_cutoff` and `late_scope`, while still requiring every EIP to receive an individual assessment.

Validate the structured records and render their cutoffs over the approved Task 04 EL timelines:

```bash
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04b-fork-evaluation-cutoffs/scripts/validate_outputs.py
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04b-fork-evaluation-cutoffs/scripts/render_review.py --validate-only
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04b-fork-evaluation-cutoffs/scripts/render_review.py
```

Later fork reports must preserve three views from unchanged original EIP scores: the primary initial-forecast total, the complete final-scope total, and the late-scope increment. A late companion may be analytically attributed to an earlier EIP, but its score is never silently transferred to that EIP.

The five current cutoff records are proposals. Inspect the interactive review plots and underlying cited scope evidence before changing `review.status` to `approved`.

## Task 05: isolated complexity assignment

Read `research/tasks/05-retrospective-complexity-assignment/TASK.md` and its `README.md` completely.

Task 05 consumes an approved Task 04 ref and packages exactly the permitted historical EIP text, pinned rubric, and allowlisted contemporaneous supporting material. One fresh `gpt-5.6-sol` session at `xhigh` assesses one EIP. The assessor sees only the sealed capsule, cannot access the network, repository, vault, other EIPs, or prior assessments, and writes only `assessment.yaml`.

Rebuild and validate deterministic packages from the repository root:

```bash
uv run --project research/tasks/05-retrospective-complexity-assignment --locked python research/tasks/05-retrospective-complexity-assignment/scripts/prepare_inputs.py --fork FORK
uv run --project research/tasks/05-retrospective-complexity-assignment --locked python research/tasks/05-retrospective-complexity-assignment/scripts/validate_inputs.py --fork FORK
```

Preview or run pending isolated sessions from the Task 05 directory:

```bash
cd research/tasks/05-retrospective-complexity-assignment
uv run --locked python scripts/run_fork.py --fork FORK --jobs 3 --dry-run
uv run --locked python scripts/run_fork.py --fork FORK --jobs 3
```

All 49 packages are sealed and validated. The 12 Osaka assignments are already complete; Shanghai, Cancun, Prague, and Amsterdam contain 37 pending assignments. The orchestrator skips canonical outputs that already exist. Do not delete or overwrite an original assessment to force a rerun; independent verification belongs to Task 06 and must preserve the original score.

Task 05 excludes opportunistic execution-specs and execution-spec-tests evidence from primary assessor packages. Exact immutable links to those repositories are retained only as manifest provenance and never enter `assessment_source_files`. A Danos checklist may be configured per fork through a machine-local path; when none is configured, the validated canonical output remains the completion record.

## Deterministic rerender check

For a configured fork, hash the output directory, rerender from unchanged inputs, and require an empty diff. For example:

```bash
find research/tasks/03-fork-development-timelines/outputs/osaka -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/osaka-before.sha256
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/03-fork-development-timelines/scripts/render.py --fork osaka
find research/tasks/03-fork-development-timelines/outputs/osaka -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/osaka-after.sha256
diff -u /tmp/osaka-before.sha256 /tmp/osaka-after.sha256
```

Repeat the same procedure for `research/tasks/04-complexity-assessment-ref-selection/outputs/review/<fork>` and `research/tasks/04b-fork-evaluation-cutoffs/outputs/review/<fork>` after running their respective `render_review.py` scripts.

## Viewing offline plots

Open an HTML file directly, or serve an output directory on a trusted local network:

```bash
python3 -m http.server 8000 --bind 0.0.0.0 --directory research/tasks/04-complexity-assessment-ref-selection/outputs/review/osaka
```

Use `hostname -I` to identify the machine's LAN address and stop the server with Ctrl-C. Do not expose the server to an untrusted network.

## Known reproducibility gaps

- Task 04b cutoff proposals still require human review; causal attribution for some late additions remains explicitly hypothetical.
- Human Task 04 approval is recorded in each EIP record, but fork-level proposal logs are not yet standardized for every fork.
- The historical execution-specs and execution-spec-tests feasibility study is not yet complete, so Task 05 supporting-evidence policy remains EIP-only.
- Task 05 launcher paths for Codex and the Danos checklist are machine-specific.
- Task 06 independent verification is not yet defined.

These gaps should be resolved before claiming that a clean checkout can reproduce the complete study without local operator knowledge.
