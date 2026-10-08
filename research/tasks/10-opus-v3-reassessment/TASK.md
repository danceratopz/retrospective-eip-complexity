# Task 10: Reassess the study with Claude Opus 5.5 and checklist revision 3

## Objective

Re-assess every EIP of the retrospective study and the current Hegotá candidates the same way, with Claude Opus 5.5 and complexity checklist revision 3, so that fork totals and the Hegotá scope can be compared on one footing. Opus 5.5 · v3 is the study's primary evaluation from this task on; the Task 05 and Task 08 GPT-5.6 · v2 results stay unchanged and selectable.

This is a separate, labelled study as Task 08 requires for a rubric change. It never edits Task 05 or Task 08 files, and its retrospective and prospective records stay in separate trees.

## Settings

| Setting | Value |
| --- | --- |
| Model | `claude-opus-5-5`, effort `high`, one run per EIP |
| Advisor or fallback model | none; a refused or failed call is recorded and retried, never served by another model |
| Rubric | `ethspecs/pm` `fe2f793b031adbb17826cfebd5bd2b502d1885c1` ([ethspecs/pm#147](https://github.com/ethspecs/pm/pull/147)), `Templates/EIP-Complexity-Assessment.md`, blob `b7c22e624c7908580a9274a8c7139ab398155dbb`, SHA-256 `70cf300b…b6f108`, checklist revision 3 |
| Assessor view | `remove_revision_notes_v1`: the `##### Revision Notes` section and its link are removed because they contain calibration scores for EIP-7928; SHA-256 `b20f6319…851cfc` |
| Engine | Claude Code headless `claude -p` with `--tools ""`, `--strict-mcp-config`, `--disable-slash-commands`, `--no-session-persistence`, `--output-format json`, the task's `--system-prompt` and a per-EIP `--json-schema` |
| Isolation | `bubblewrap_claude_p_no_tools_v1`: a bubblewrap capsule whose home holds only `~/.claude/.credentials.json`; no tools, MCP servers, skills, settings, memory or project files |
| Concurrency | 4 |

`config.yaml` is authoritative for these pins.

## Procedure

Score only, mirroring Task 05's contract: 28 criteria in rubric order, one permitted level each, evidence locators, rationale, confidence, an uncertainty note, and a separate under-specification record. There is no spec-quality review stage and no refutation call.

The model receives one prompt per EIP containing every package document verbatim (target EIP and allowlisted supporting documents), the assessor view, the candidate interacting EIPs and [`prompts/assessment-contract.md`](prompts/assessment-contract.md), with [`prompts/system.md`](prompts/system.md) as the system prompt. The output is constrained by a JSON schema generated from the template: permitted levels per criterion (0–3 plus exceptional 4; 0, 3 and 4 for the five binary criteria), evidence sources limited to the package documents, and interacting EIPs limited to those the target names in its text or `requires`.

Totals, the cross-EIP bonus and tiers are computed mechanically:

- `cross_eip_interactions.score` = the model's level (`base_score`) + `bonus`, where the bonus is +1 for every 3 interacting EIPs needing target-specific coordinated cases beyond the first 3 (`bonus_qualifying_eips`). Local compatibility checks do not count.
- `totals.primary_score` is the sum of the 28 criterion scores; the tier uses the template's thresholds (<12 low, 12–22 medium, ≥23 high), which equal Task 05's.
- The plausible total range is the primary total adjusted by the model's per-criterion minimum and maximum levels (`under_specification.criterion_ranges`).

Each response is converted into the Task 05 assessment YAML shape (retrospective) or the Task 08 shape (prospective) and validated by `scripts/validate.py`, which reuses the Task 05 validator's tier, range and evidence helpers with the v3 pins.

## Retrospective tree

The 49 EIPs of Task 05 (Shanghai 5, Cancun 6, Prague 11, Osaka 12, Amsterdam 15), each from its sealed Task 05 package at its Task 04 reference commit. Only the rubric changes:

- `retrospective/inputs/packages/<fork>/eip-<n>/` reuses `eip.md` and `supporting/` byte-for-byte from the Task 05 package (verified against the Task 05 manifest) and replaces `rubric.md` and `output-template.yaml`. The manifest references the Task 05 package and manifest by path and SHA-256.
- The prompt states the fork, the historical revision and information cutoff, and the baseline: the preceding mainnet fork plus the changes the EIP requires.
- Outputs: `retrospective/outputs/assessments/<fork>/eip-<n>.yaml` and raw `claude -p` JSON in `retrospective/outputs/raw/<fork>/eip-<n>.json`.

Fork totals use the Task 04b `included_at_cutoff` cohorts, as for Task 05.

## Prospective tree

The EIP-8081 Scheduled (SFI), Considered (CFI) and Proposed (PFI) for Inclusion entries at `ethereum/EIPs` `6dac5e74918b54511298fdbff79650e8f8d27d78` (committed 2026-10-07T22:23:55Z; `../EIPs` pulled 2026-10-08T09:12:50Z with no newer commit). Declined (DFI) entries are out of scope.

- `prospective/inputs/cohort.yaml` freezes EIP-8081's blob and the 35 entries with their list (2 SFI, 12 CFI, 21 PFI).
- `prospective/inputs/cohort-review.yaml` applies Task 08's layer-applicability gate. Dispositions the project owner approved in Task 08 are reused; the seven EIPs added since are proposed by the coordinator and marked `proposed_pending_owner_review`. Consensus-only and informational, nonbinding entries are `not_applicable_to_el_rubric` and get no score or tier.
- Packages follow Task 08's package policy through the Task 05 `supporting_documents` engine at the snapshot commit; consensus-spec links stay provenance only. The prompt's baseline is Amsterdam plus the changes the EIP requires.
- Outputs: `prospective/outputs/assessments/hegota-2026-10-08/eip-<n>.yaml` and raw JSON under `prospective/outputs/raw/hegota-2026-10-08/`. Each record carries its EIP-8081 list and the EIPs commit.

## Do not reuse

The Opus results in `eip-complexity/data/study-2026-10-08/llm/` reviewed the specification before scoring, used a different package format and are not inputs to this task. They are a documented fallback only.

## Provenance

Every assessment records the task ID, model, effort, Claude Code version and exact flags; system-prompt, prompt and schema SHA-256; the package manifest (EIPs commit, path, Git blob and SHA-256 of every document); rubric pins and assessor-view hash; start and end times; Claude Code's usage and cost report; and the raw output path and hash. The runner rebuilds each prompt and refuses to send it if its hash differs from the package manifest, refuses to run with uncommitted Task 10 inputs or scripts, and records each run's commit and Claude Code version in `runs/`.

## Reproduce

From the repository root, with complete clones of `ethereum/EIPs` and `ethspecs/pm`, a logged-in `claude` CLI and `bwrap`:

```bash
P=research/tasks/05-retrospective-complexity-assignment
T=research/tasks/10-opus-v3-reassessment/scripts
uv run --project $P --locked python $T/prepare.py --eips-repo ../EIPs --pm-repo ../pm
uv run --project $P --locked python $T/prepare.py --eips-repo ../EIPs --pm-repo ../pm --check
uv run --project $P --locked python $T/run.py --only shanghai/3855 amsterdam/7928 hegota/8141   # pilot
uv run --project $P --locked python $T/run.py                                                  # all; resumes
uv run --project $P --locked python $T/validate.py
uv run --project $P --locked python $T/summarize.py
```

`run.py` keeps every successful raw response and skips it on the next run; failed calls are kept under `outputs/failed/` and retried. `run.py --convert-only` rebuilds the assessment YAML from raw responses without new calls.

## Limitations

- The capsule controls what the model reads, not what it remembers. Opus 5.5 may recall Shanghai through Osaka outcomes; the GPT-5.6 run had the same exposure.
- Locators cite section headings rather than line numbers, because the model reads embedded documents without file tools.
- v3 totals are not interchangeable with v2 totals; the template says scores are not comparable across revisions.
- The seven new Hegotá dispositions await owner review.
