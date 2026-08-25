# Task 05 isolated run guide

Approved Task 04 refs can be sealed for one fresh assessment session per EIP. The assessor must not run in this repository: it would be able to see completed assignments and other hindsight-bearing research. Use the launcher below, which creates a one-EIP capsule and hides the repository, vault, prior run capsules, global Codex state, and all other assessment inputs from the assessor process.

Different EIPs may run in parallel. A non-blocking per-EIP lock prevents two sessions for the same EIP.

## Start a session

From a normal terminal, run:

```bash
cd /home/dtopz/code/github/retrospective-complexity-eval/research/tasks/05-retrospective-complexity-assignment
uv run --locked python scripts/run_isolated.py --fork FORK --eip NNNN
```

Replace `FORK` and `NNNN` with one prepared fork and EIP number. The launcher runs non-interactive Codex with `gpt-5.6-sol` at `xhigh`; there is no TUI to close. When Codex finishes, the launcher validates `assessment.yaml` and imports it to the canonical output path without overwriting an existing result. When a shared checklist is configured, it is ticked under a lock; otherwise the canonical output is the completion record.

If the launcher is interrupted after `assessment.yaml` was written, recover the retained capsule without rerunning the assessment:

```bash
uv run --locked python scripts/run_isolated.py --fork FORK --eip NNNN --collect-capsule /tmp/retrospective-complexity-assessment-runs/CAPSULE_DIRECTORY
```

Do not open a Codex session at the repository root and paste a prompt path. Changing the working directory alone is also insufficient; only the isolated launcher enforces the filesystem boundary.

For manual troubleshooting only, add `--interactive` to use the TUI.

To test the boundary without starting an assessment or consuming model tokens:

```bash
uv run --locked python scripts/run_isolated.py --fork FORK --eip NNNN --verify-isolation
```

## Prepared sessions

Prepared packages and prompts live under `inputs/fork-eips/<fork>/eip-<number>/` and `prompts/<fork>/eip-<number>.md`. Completed assessments live under `outputs/fork-eips/<fork>/eip-<number>.yaml`.

| Fork | Prepared | Complete | Pending |
| --- | ---: | ---: | ---: |
| Shanghai | 5 | 0 | 5 |
| Cancun | 6 | 0 | 6 |
| Prague | 11 | 0 | 11 |
| Osaka | 12 | 12 | 0 |
| Amsterdam | 15 | 0 | 15 |
| Total | 49 | 12 | 37 |

## Run all pending EIPs

Preview the pending inventory without launching model sessions:

```bash
uv run --locked python scripts/run_fork.py --fork FORK --jobs 3 --dry-run
```

Run all pending EIPs with at most three isolated, non-interactive sessions at once:

```bash
uv run --locked python scripts/run_fork.py --fork FORK --jobs 3
```

Each session gets a separate capsule, output, lock, and log. The orchestrator skips existing canonical outputs, records a run manifest under `runs/`, and continues independent sessions if one EIP fails validation.

## Rebuild inputs

Preparation requires local `ethereum/EIPs` and `ethspecs/pm` clones. The `ethereum/consensus-specs` clone is used only when an approved EIP revision directly links an immutable file from it. From the repository root:

```bash
uv run --project research/tasks/05-retrospective-complexity-assignment --locked python research/tasks/05-retrospective-complexity-assignment/scripts/prepare_inputs.py --fork FORK
```

The generated packages and prompts are deterministic. Completed outputs are never overwritten, and their existing packages are skipped. Do not rebuild pending packages while assessment sessions are active. Execution-specs and execution-spec-tests links are recorded as provenance only and never enter the assessor source allowlist.

Validate the sealed inventory before launching sessions:

```bash
uv run --project research/tasks/05-retrospective-complexity-assignment --locked python research/tasks/05-retrospective-complexity-assignment/scripts/validate_inputs.py --fork FORK
```
