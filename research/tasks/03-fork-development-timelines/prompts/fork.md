# Fresh-agent prompt: Task 03 for `<FORK>`

Work locally in `/home/dtopz/code/github/retrospective-complexity-eval` and complete Task 03 for exactly one fork: `<FORK>`.

Replace `<FORK>` everywhere with the canonical lowercase fork ID. The configured study IDs are `shanghai`, `cancun`, `prague`, `osaka`, and `amsterdam`. Do not work in the original `pm.retrospective-complexity-eval` staging directory, and do not commit or push changes.

## Objective

Complete the applicable Task 03 phase for `<FORK>`:

- **Task 03A — assemble canonical timeline data:** run once when the normalized fork milestone, devnet, and per-EIP participation inputs do not yet exist.
- **Task 03B — render fixed timeline data:** validate and deterministically render the canonical inputs without researching or changing them.

Both phases ultimately support three figure families:

1. a fork overview;
2. execution-layer EIP histories; and
3. consensus-layer EIP histories.

The figures are evidence for later human review. Do not select a complexity-assessment ref, infer a final development-start date, assign complexity scores, inspect client implementation effort, or investigate historical `execution-specs`/`execution-spec-tests` suitability in this task.

## Read first

Read these files completely before editing anything:

1. `README.md`
2. `REPRODUCING.md`
3. `research/README.md`
4. `research/tasks/03-fork-development-timelines/TASK.md`
5. `research/tasks/03-fork-development-timelines/templates/fork-input.yaml`
6. `research/tasks/03-fork-development-timelines/templates/source-registry.yaml`

Then check whether both target files already exist:

```text
research/tasks/03-fork-development-timelines/inputs/forks/<FORK>.yaml
research/tasks/03-fork-development-timelines/inputs/sources/<FORK>.yaml
```

If both exist, read them completely and treat them as fixed canonical inputs: perform Task 03B only. Do not re-research, rewrite, or “refresh” their evidence merely because newer mutable pages exist. If neither exists, perform Task 03A followed by Task 03B. If only one exists, stop and report the inconsistent partial state before editing.

Amsterdam and Osaka are optional implementation examples only when a template field remains unclear. Their contents are never evidence for `<FORK>` and must not be copied as assumptions.

Treat Task 01 as authoritative for fork membership, EIP layers, creation dates, EIP-file revisions, semantic classifications, and inclusion-state events. Do not modify Task 01 records during this task.

## Ownership boundary

Write only:

```text
research/tasks/03-fork-development-timelines/inputs/forks/<FORK>.yaml
research/tasks/03-fork-development-timelines/inputs/sources/<FORK>.yaml
research/tasks/03-fork-development-timelines/outputs/<FORK>/
```

The renderer owns the complete output directory. Never hand-edit generated HTML, SVG, PDF, Vega-Lite JSON, `plot-data.json`, or `plot-manifest.yaml`.

Preserve unrelated work and report any conflict.

## Task 03A: assemble canonical timeline data

Skip this entire section when both target input files already exist.

### Evidence policy

Internet access is permitted for Task 03 evidence discovery. Prefer primary, immutable sources and locally available full-history clones. Relevant local repositories may exist beside this repository, including `EIPs`, `forkcast`, `homepage`, fork-specific EthPandaOps devnet repositories, `consensus-specs`, `execution-specs`, and `pm`. Treat adjacent repositories as read-only.

For every normalized observation:

- add one or more source-registry entries with stable IDs;
- use an immutable Git commit/blob/tree permalink whenever the evidence exists in Git;
- retain the original HackMD or network page as a discovery/canonical URL where useful;
- do not rely on a mutable web page alone when a pinned repository representation exists;
- preserve the source's actual date precision rather than inventing a timestamp;
- record confidence and concise ambiguity notes; and
- use quoted ISO 8601 dates.

Do not infer that every fork EIP participated in every devnet. Apply the participation bases defined by Task 03 exactly: `explicit_eip_list`, `explicit_protocol_config`, `fork_spec_activation`, or `series_scope`. Use `series_scope` only for a narrowly feature-specific series with evidence supporting that interpretation.

Distinguish actual launches from planned, cancelled, and unverified networks. Planned or cancelled devnets must not be presented as actual. When the evidence cannot support a normalized observation, preserve it under `unknowns` with the source and explanation rather than guessing.

### Assembly procedure

1. Inspect the Task 01 fork record and all fork–EIP records for `<FORK>`. Establish the authoritative EIP inventory and expected EL, CL, and cross-layer membership.
2. Identify the fork's execution name, consensus name, combined/common name, mainnet activation, public testnet activations, fork-definition milestones, and any other dated fork milestone that materially orients the development timeline. Do not duplicate EIP-level inclusion events already owned by Task 01.
3. Reconstruct every relevant devnet series from the earliest attributable launch through the fork activation or latest available evidence. For each devnet, establish:
   - identifier and series;
   - launch date or timestamp;
   - status;
   - participating EIPs;
   - participation basis;
   - affected layer or layers, derived from Task 01 classifications;
   - evidence, confidence, and ambiguity notes.
4. Create `inputs/sources/<FORK>.yaml` before referencing its source IDs from the fork input. Match the existing source-registry structure.
5. Create `inputs/forks/<FORK>.yaml`. Reference the existing Task 01 records by relative path. Choose one shared plot window that makes the fork's development period legible while preserving cumulative left-edge baselines for earlier EIP revisions.
6. Check mechanically that:
   - every milestone and devnet source ID resolves;
   - every participating EIP belongs to the Task 01 fork inventory;
   - every layer assignment follows Task 01;
   - no planned/cancelled devnet is represented as an actual launch; and
   - cross-layer EIPs will appear in both layer figures.
After completing these inputs, they become the fixed Task 03 dataset consumed by rendering, assessment-ref review, and later tasks. Later agents must not independently reconstruct devnet participation.

## Task 03B: validate and render fixed data

Task 03B does not require internet access or new evidence gathering. Use the existing target inputs, whether accepted from an earlier run or just completed by Task 03A.

1. Validate only this fork from the repository root:

   ```bash
   uv sync --project research/tasks/03-fork-development-timelines --locked
   uv run --project research/tasks/03-fork-development-timelines --locked \
     python research/tasks/03-fork-development-timelines/scripts/render.py \
     --validate-only --fork <FORK>
   ```

2. Resolve mechanical validation errors. If validation exposes a substantive problem in already-fixed evidence, do not silently repair it: report the problem and the source record that requires human review. Do not weaken the renderer or validation rules.
3. Generate all artifacts through the renderer:

   ```bash
   uv run --project research/tasks/03-fork-development-timelines --locked \
     python research/tasks/03-fork-development-timelines/scripts/render.py \
     --fork <FORK>
   ```

4. Inspect the generated `plot-data.json`, `plot-manifest.yaml`, SVGs, and HTML figures. Confirm that event labels, cumulative revision histories, layer membership, devnet relevance, calendar range, and source links are intelligible and internally consistent.
5. Re-run validation and rendering once from unchanged inputs. Compare output hashes and require an empty deterministic diff, following the procedure in `REPRODUCING.md`.

## Completion report

Return a concise report containing:

- the fork ID and display names used;
- whether Task 03A was required or the canonical inputs already existed;
- Task 01 inventory counts for all, EL, CL, and cross-layer EIPs;
- milestone and devnet counts, separated by status;
- for Task 03A, the evidence sources and local repositories consulted;
- all unresolved or low-confidence observations;
- the exact validation and render commands run and their results;
- confirmation that the second render was byte-identical; and
- the files changed.

Stop after Task 03 is complete. Leave assessment-ref selection, historical code-snapshot selection, and complexity assignment to their separate tasks.
