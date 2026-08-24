# Task 05 isolated run guide

The Osaka assessment inputs are sealed and ready for one fresh session per EIP. The assessor must not run in this repository: it would be able to see completed assignments and other hindsight-bearing research. Use the launcher below, which creates a one-EIP capsule and hides the repository, vault, prior run capsules, global Codex state, and all other assessment inputs from the assessor process.

Different EIPs may run in parallel. A non-blocking per-EIP lock prevents two sessions for the same EIP.

## Start a session

From a normal terminal, run:

```bash
cd /home/dtopz/code/github/retrospective-complexity-eval/research/tasks/05-retrospective-complexity-assignment
uv run --locked python scripts/run_isolated.py --fork osaka --eip NNNN
```

Replace `NNNN` with one prepared EIP number. The launcher runs non-interactive Codex with `gpt-5.6-sol` at `xhigh`; there is no TUI to close. When Codex finishes, the launcher validates `assessment.yaml`, imports it to the canonical output path without overwriting an existing result, and ticks the vault checklist under a lock.

If the launcher is interrupted after `assessment.yaml` was written, recover the retained capsule without rerunning the assessment:

```bash
uv run --locked python scripts/run_isolated.py --fork osaka --eip NNNN --collect-capsule /tmp/retrospective-complexity-assessment-runs/CAPSULE_DIRECTORY
```

Do not open a Codex session at the repository root and paste a prompt path. Changing the working directory alone is also insufficient; only the isolated launcher enforces the filesystem boundary.

For manual troubleshooting only, add `--interactive` to use the TUI.

To test the boundary without starting an assessment or consuming model tokens:

```bash
uv run --locked python scripts/run_isolated.py --fork osaka --eip NNNN --verify-isolation
```

## Prepared Osaka sessions

| EIP | Canonical prompt provenance | Canonical output |
|---:|---|---|
| 7594 | `prompts/osaka/eip-7594.md` | `outputs/fork-eips/osaka/eip-7594.yaml` |
| 7642 | `prompts/osaka/eip-7642.md` | `outputs/fork-eips/osaka/eip-7642.yaml` |
| 7823 | `prompts/osaka/eip-7823.md` | `outputs/fork-eips/osaka/eip-7823.yaml` |
| 7825 | `prompts/osaka/eip-7825.md` | `outputs/fork-eips/osaka/eip-7825.yaml` |
| 7883 | `prompts/osaka/eip-7883.md` | `outputs/fork-eips/osaka/eip-7883.yaml` |
| 7892 | `prompts/osaka/eip-7892.md` | `outputs/fork-eips/osaka/eip-7892.yaml` |
| 7910 | `prompts/osaka/eip-7910.md` | `outputs/fork-eips/osaka/eip-7910.yaml` |
| 7918 | `prompts/osaka/eip-7918.md` | `outputs/fork-eips/osaka/eip-7918.yaml` |
| 7934 | `prompts/osaka/eip-7934.md` | `outputs/fork-eips/osaka/eip-7934.yaml` |
| 7935 | `prompts/osaka/eip-7935.md` | `outputs/fork-eips/osaka/eip-7935.yaml` |
| 7939 | `prompts/osaka/eip-7939.md` | `outputs/fork-eips/osaka/eip-7939.yaml` |
| 7951 | `prompts/osaka/eip-7951.md` | `outputs/fork-eips/osaka/eip-7951.yaml` |

## Run all pending EIPs

Preview the pending inventory without launching model sessions:

```bash
uv run --locked python scripts/run_fork.py --fork osaka --jobs 3 --dry-run
```

Run all pending EIPs with at most three isolated, non-interactive sessions at once:

```bash
uv run --locked python scripts/run_fork.py --fork osaka --jobs 3
```

Each session gets a separate capsule, output, lock, and log. The orchestrator skips existing canonical outputs, records a run manifest under `runs/`, and continues independent sessions if one EIP fails validation.

## Rebuild inputs

Preparation requires local `ethereum/EIPs`, `ethspecs/pm`, and `ethereum/consensus-specs` clones. From the repository root:

```bash
uv run --project research/tasks/05-retrospective-complexity-assignment --locked python research/tasks/05-retrospective-complexity-assignment/scripts/prepare_inputs.py --fork osaka
```

The generated packages and prompts are deterministic. Do not rebuild them while assessment sessions are active.

Validate the sealed inventory before launching sessions:

```bash
uv run --project research/tasks/05-retrospective-complexity-assignment --locked python research/tasks/05-retrospective-complexity-assignment/scripts/validate_inputs.py --fork osaka
```
