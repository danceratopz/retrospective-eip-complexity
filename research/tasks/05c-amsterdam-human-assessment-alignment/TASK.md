# Task 05c: Compare Amsterdam human and automated complexity assessments

## Objective

Measure how closely a blinded automated assessor reproduces the historical human complexity assessments for Amsterdam EIPs when both use the checklist that was available to the human reviewer.

The automated historical-checklist run must reuse the exact approved Task 04 EIP revision and sealed supporting evidence already used by the primary Task 05 assessment. The only intended assessment-input change is the rubric revision. Human assessments remain hidden until each automated result has been validated and hash-frozen.

This is a calibration and evaluator-alignment study. Its scores are not primary retrospective scores, do not replace Task 05 outputs, and must not enter fork totals.

## Questions

The task answers three related questions:

1. Human–automated alignment: With the historical checklist, how closely does the blinded automated result match the original human result?
2. Rubric-revision effect: For the same approved historical EIP input, how does the automated historical-checklist result differ from the existing automated checklist-revision-2 result?
3. Input-state confounding: Did the human reviewer assess a materially different EIP revision from the approved Task 04 revision?

The first comparison is the primary output of this task. The second is a controlled rubric sensitivity comparison. The third determines which human–automated comparisons are clean enough to aggregate.

## Relationship to other tasks

- Task 04 provides the human-approved historical EIP revision and information cutoff. Reuse it without alteration.
- Task 05 provides the sealed evidence package and the automated checklist-revision-2 assessment. Treat both as immutable inputs.
- Task 05b may freeze the primary assessment dataset independently. This task does not block or modify that freeze.
- Task 06 remains the independent verification of primary Task 05 results. This task is not a substitute for it.
- Task 07 and later observed-effort analysis must not use Task 05c scores as primary predictions.

## Canonical local sources

- Research repository: /home/dtopz/code/github/retrospective-complexity-eval
- PM repository: /home/dtopz/code/github/pm
- EIP repository: /home/dtopz/code/github/EIPs
- Approved Amsterdam refs: research/tasks/04-complexity-assessment-ref-selection/outputs/fork-eips/amsterdam/
- Sealed Amsterdam packages: research/tasks/05-retrospective-complexity-assignment/inputs/fork-eips/amsterdam/
- Current automated results: research/tasks/05-retrospective-complexity-assignment/outputs/fork-eips/amsterdam/
- Historical human assessments in PM: complexity_assessments/EIPs/EIP-*.md
- Historical checklist in PM: Templates/EIP-Complexity-Assessment.md

Keep all source discovery local. Do not fetch, browse, search the internet, or substitute current web content for local Git history.

## Read first

Read these files completely before implementing or running the task:

- this task;
- research/tasks/04-complexity-assessment-ref-selection/TASK.md;
- every approved Amsterdam Task 04 output;
- research/tasks/05-retrospective-complexity-assignment/TASK.md;
- research/tasks/05-retrospective-complexity-assignment/README.md;
- the Task 05 input-preparation, input-validation, isolated-launch, output-validation, and fork-run scripts;
- the Task 05 rubric manifest and assessor view;
- prompts/coordinator.md in this task; and
- prompts/assessor.md in this task.

Record the research-repository, PM-repository, and EIP-repository HEADs and dirty states before acting. Preserve unrelated work and never stage another task's changes.

## Study design

Use three independently preserved observations:

| ID | Observation | EIP input | Rubric | Evaluator |
| --- | --- | --- | --- | --- |
| A | Primary retrospective assessment | Approved Task 04 revision | Checklist revision 2 | Existing isolated automated assessor |
| B | Historical-checklist replication | Same approved Task 04 revision as A | Checklist used for the human assessment | New isolated automated assessor |
| C | Published human assessment | EIP state available to the human reviewer | Checklist used for that human assessment | Original human reviewer |

Interpret the comparisons as follows:

- B versus C estimates human–automated alignment, subject to EIP-input drift and historical timing.
- A versus B estimates the effect of changing the rubric while holding the EIP input, evidence package, model, reasoning effort, and isolation design as constant as practical.
- A versus C is descriptive only. It combines evaluator, rubric, and possibly EIP-state differences and must not be presented as a controlled comparison.

Do not tune prompts, mappings, scoring rules, or weights after looking at which version improves agreement.

## Study population

Derive the population mechanically as the intersection of:

1. EIPs with approved Task 04 Amsterdam records;
2. completed historical human assessment files reachable in the local PM history; and
3. existing valid Task 05 Amsterdam packages and outputs.

Do not assume that every final Amsterdam EIP has a human assessment. Record excluded EIPs and the exact reason, such as no historical human assessment, incomplete human score, missing Task 05 output, or unresolved provenance.

The PM calibration dataset is not authoritative for this population. It represents a test-suite intersection assembled for another purpose and may include or exclude different EIPs.

## Approved EIP reference policy

The approved Task 04 reference is authoritative for observation B. Do not select a new EIP ref for this task and do not replace it with the EIP revision that the human reviewer saw.

For every included EIP:

- copy the historical EIP identity, commit, Git blob SHA, content SHA-256, immutable URL, committed timestamp, and information cutoff from the existing sealed Task 05 package;
- mechanically verify the blob and hashes against the local EIPs repository;
- reuse the same supporting-document allowlist and exact blobs as Task 05;
- remove the checklist-revision-2 rubric and output template from the copied package; and
- insert only the verified historical rubric and an output template generated from that rubric.

This creates a controlled A-versus-B comparison. A different EIP version may be reconstructed only for the C input-drift audit, never shown to the automated assessor.

## Reconstruct the human assessment event

For every candidate PM assessment file, inspect its complete Git history. Classify each commit that changed the file as one of:

- initial substantive scoring;
- substantive score change;
- substantive rationale change;
- rubric or anchor-definition change;
- title, link, formatting, or other editorial change; or
- ambiguous.

Select the human assessment event as the latest commit in the authoritative initial review sequence that materially established or changed scores or score rationales. Do not use a later title or link cleanup as the assessment date.

Preserve:

- PM repository commit and timestamp;
- file path, Git blob SHA, content SHA-256, and immutable URL;
- complete commit classification history;
- raw score cells exactly as published;
- mechanically parsed numeric contributions;
- published total and tier;
- recomputed total and tier;
- parser notes and unresolved ambiguities; and
- the evidence for choosing the event.

Human score cells may be blank or may contain expressions such as 2 + 2 + 3. Preserve the raw cell and parse only a narrowly defined grammar. Never silently treat a blank as zero unless the published arithmetic and surrounding file make that interpretation explicit. If total reconstruction remains ambiguous, retain the record but exclude it from numeric aggregate comparisons.

## Resolve the historical checklist

Do not hardcode one campaign-wide checklist commit without verification. For each selected human assessment event:

1. Resolve the latest commit to Templates/EIP-Complexity-Assessment.md at or before the human event timestamp.
2. Record its repository commit, timestamp, path, Git blob SHA, content SHA-256, immutable URL, anchor order, anchor definitions, score domains, maximum score, and tier thresholds.
3. Compare the human assessment's embedded anchors and definitions with that template.
4. Classify the match as:
   - exact: anchor inventory, definitions, score domains, and thresholds match;
   - compatible: only non-semantic presentation differences exist;
   - divergent: a scoring-relevant difference exists; or
   - unknown: the relationship cannot be resolved.
5. Use the exact verified rubric applicable to that human event for observation B.

If the human file and the time-resolved template diverge, preserve both sources. Do not silently choose whichever produces better agreement. Mark the comparison confounded and explain which rubric the automated run used. A clean aggregate requires an exact or compatible template match.

Local history currently suggests template commits around 2025-10-31 and 2025-11-05, followed by checklist revision 2 in 2026. These are discovery leads, not authoritative pins; verify every full commit and blob.

## Reconstruct the EIP state visible to the human

For each human assessment event, resolve the latest EIPS/eip-NNNN.md commit whose committer time is at or before the event. Record its full commit, timestamp, Git blob SHA, content SHA-256, and immutable URL.

Compare that blob with the approved Task 04 blob using the Task 01 substantive-versus-editorial definition and classify input alignment as:

- exact_blob: identical Git blob;
- no_substantive_drift: different blob, but only editorial or non-semantic changes;
- substantive_drift: one or more substantive specification changes;
- unknown: history or classification is insufficient.

Record every intervening EIP commit and its classification. Summarize substantive differences without using them to alter observation B.

Also record whether the human review occurred after visible implementation, devnet, testing, or fork-development evidence that could have affected human judgment. This is a human-timing confound, not contamination of the original historical record. Use:

- low_exposure;
- possible_exposure;
- high_exposure; or
- unknown.

The clean human–automated aggregate includes only exact_blob or no_substantive_drift records with exact or compatible rubric matches and an unambiguous human total. Report all other rows descriptively.

## Blinding and hindsight firewall

The coordinator may reconstruct human data, but no automated assessor capsule may contain or reveal:

- the human assessment file, score, tier, rationale, author, or assessment commit;
- the study's human-alignment hypothesis or expected result;
- another EIP's package or score;
- the existing Task 05 assessment or checklist-revision-2 rubric;
- PM calibration files or observed-effort data;
- present-day or later EIP revisions;
- client implementations, execution-specs, execution-spec-tests, devnets, bugs, outcomes, or test effort;
- the project repository, Danos vault, global Codex state, skills, plugins, apps, browsers, MCP servers, or internet access.

The capsule must contain only:

    /mnt/workspace/
        ASSESSMENT-CONTRACT.md
        PROMPT.md
        package/
            manifest.yaml
            eip.md
            rubric.md
            output-template.yaml
            supporting/

Generate the capsule from a positive allowlist. Test that PM human files, Task 05 outputs, comparison files, and the repository root are invisible from inside the sandbox. A visible URL is provenance, not permission to browse.

No dedicated complexity-assessment skill may be used. Latent model knowledge cannot be removed; require package-grounded evidence for every score and record that limitation in the final report.

If prohibited information is exposed before output completion, require a contaminated attestation, reject the output as authoritative, preserve the incident record, and do not quietly rerun until the cause is understood.

## Automated historical-checklist assignment

Run one fresh isolated assessor session per EIP.

- Model: gpt-5.6-sol
- Reasoning effort: xhigh
- Maximum concurrent assessors: 3
- Approval policy: never
- Internet: forbidden and technically disabled
- Working directory: the one-EIP bubblewrap capsule at /mnt/workspace
- Output: only /mnt/workspace/assessment.yaml

Use the Task 05 isolation implementation as the reference design, but create a Task 05c-owned launcher and validator because the historical anchor inventory and thresholds differ. Do not weaken or mutate Task 05's launcher, packages, validators, prompts, or outputs.

Keep the assessment method as close to Task 05 as the historical rubric allows:

- read the complete historical rubric before scoring;
- read every sealed assessment source completely;
- apply every historical anchor in canonical order, including zero scores;
- use only scores allowed by that anchor, with score 4 only when the historical rubric expressly permits an exceptional score;
- provide package-relative evidence, concise rationale, confidence, and uncertainty for every anchor;
- preserve cross-EIP dependencies only when identified by the sealed package;
- calculate total and tier mechanically from the historical rubric;
- record material under-specification separately; and
- complete provenance and hindsight attestations.

Do not add revision-2-only criteria to the historical run. Do not reinterpret old anchors using revision-2 calibration examples.

Record the Codex executable path, version, binary SHA-256, command, model, effort, launcher hash, assessor prompt hash, sanitized contract hash, run timestamp, session ID, and isolation method.

## Freeze before comparison

The coordinator must complete these gates in order:

1. Discover and validate the human event, historical rubric, and input-drift record.
2. Prepare and validate every sealed automated package without human material.
3. Run the isolated historical-checklist assessments.
4. Validate each automated output and copy it into a non-overwriting canonical path.
5. Produce a freeze manifest containing each automated output hash and package hash.
6. Verify that regenerating the freeze manifest without changed inputs is byte-identical.
7. Only then import human scores into comparison records and calculate alignment.

The comparison script must refuse to run when the freeze manifest is missing, stale, or inconsistent.

## Work unit

Keep all new permanent files under this task directory:

    research/tasks/05c-amsterdam-human-assessment-alignment/
        TASK.md
        prompts/
            coordinator.md
            assessor.md
        templates/
            human-assessment.yaml
            automated-assessment.yaml
            comparison.yaml
        inputs/
            study-inventory.yaml
            rubrics/
            human/
            packages/
        outputs/
            automated/
            comparisons/
            automated-freeze.yaml
            dataset-manifest.yaml
            alignment-summary.md
        scripts/
            discover_human_assessments.py
            prepare_inputs.py
            validate_inputs.py
            run_isolated.py
            run_study.py
            import_human_assessments.py
            compare.py
            validate_outputs.py

The coordinator may choose different script decomposition when justified, but the data boundaries must remain explicit: source reconstruction, blinded automated inputs, frozen automated outputs, revealed human inputs, and comparisons may not be collapsed into one mutable file.

Do not edit shared repository documentation while unrelated uncommitted task work is present. A later integration commit can link this work from README and REPRODUCING.

## Required structured data

### Study inventory

study-inventory.yaml must contain:

- schema and task version;
- source repository identities and HEADs;
- generation timestamp and script hash;
- all approved Amsterdam EIPs;
- inclusion or exclusion status and reason;
- Task 04 record path and hash;
- Task 05 package manifest path and hash;
- Task 05 output path and hash;
- PM human assessment path when present;
- selected human assessment event;
- resolved historical rubric identity;
- input-alignment classification;
- template-match classification;
- human-timing exposure;
- clean-comparison eligibility and explicit failed conditions; and
- the expected per-stage output paths.

### Human record

Each inputs/human/eip-NNNN.yaml must retain:

- selected human-event provenance;
- complete assessment-file commit classification;
- raw and parsed per-anchor score cells;
- raw and parsed total and tier;
- resolved checklist provenance and match result;
- human-time EIP provenance;
- intervening EIP commit classifications;
- input-alignment and timing-exposure judgments;
- evidence locators, confidence, and unresolved issues; and
- record-generation script and content hashes.

Preserve the original PM Markdown as the source of truth. The YAML is a structured extraction and must link to the exact historical blob.

### Automated result

Each outputs/automated/eip-NNNN.yaml must contain:

- historical EIP and supporting-source provenance copied from the sealed package;
- exact historical rubric provenance;
- assessor environment and isolation provenance;
- historical scope summary;
- one record per historical anchor in exact rubric order;
- score, evidence, rationale, confidence, and uncertainty;
- exceptional-score justification when applicable;
- mechanically calculated total, maximum, and tier;
- structured under-specification;
- source and operational-file attestations; and
- hindsight-control attestation.

### Comparison record

Each outputs/comparisons/eip-NNNN.yaml must contain:

- identities and hashes for A, B, and C;
- EIP-input alignment and substantive-drift evidence;
- historical-template match and timing-exposure classification;
- clean-comparison eligibility;
- human and automated historical-checklist totals and tiers;
- current automated checklist-revision-2 total and tier;
- B-minus-C signed difference and absolute error;
- A-minus-B signed difference, with differing score ranges and thresholds explicit;
- tier agreement for B versus C;
- raw and normalized per-anchor human values;
- per-anchor B-versus-C differences;
- a separately defined A-versus-B criterion mapping with exact, changed, revision-1-only, revision-2-only, or unmapped status;
- factual-disagreement, rubric-interpretation, evaluator-judgment, input-drift, and parsing notes; and
- provenance for the comparison script and all consumed inputs.

Never force unlike anchors into a one-to-one mapping. Total-score comparisons across rubric revisions must report each rubric's maximum score and tier thresholds.

### Dataset manifest and summary

dataset-manifest.yaml must inventory and hash every input, package, automated result, human record, comparison, prompt, contract, rubric, script, and source commit needed to reproduce the study.

alignment-summary.md must report:

- population and exclusions;
- exact-agreement rate;
- mean and median absolute total-score error;
- signed bias;
- rank agreement using Spearman and Kendall statistics when sample size permits;
- tier agreement and a tier-confusion table;
- per-anchor signed and absolute differences;
- clean and confounded subsets separately;
- input-drift and timing-exposure cases;
- rubric-revision effects from A versus B;
- qualitative examples of strong agreement and material disagreement; and
- limitations, especially small sample size, Amsterdam being in-sample for later rubric work, and irreducible model latent knowledge.

With a small Amsterdam sample, report descriptive statistics and uncertainty plainly. Do not optimize rubric weights, claim causal effects, or present p-values as decisive evidence.

## Validation

The task validator must at minimum:

1. derive the approved Amsterdam inventory from Task 04;
2. verify every Task 04, Task 05 package, Task 05 output, PM assessment, EIP blob, and rubric blob hash;
3. verify inclusion and exclusion reasons exhaust the inventory;
4. verify human-event and template timestamps;
5. verify parsed human totals without inventing blank scores;
6. verify automated package sources exactly match the Task 05 source allowlist except for the controlled rubric replacement;
7. scan capsule manifests and prompts for forbidden human or current-score material;
8. require one unique isolated session per automated result;
9. recompute every automated total, maximum, tier, comparison delta, and summary statistic;
10. require no hindsight contamination;
11. require an immutable automated freeze before comparisons;
12. recompute every recorded file hash; and
13. fail if any Task 04 or Task 05 input or output changed.

Run a no-token isolation self-test before real assessments. Verify filesystem hiding, no network namespace access, disabled Codex web search, no inherited MCP/apps/plugins/skills, approval policy never, and inability to read PM, the research repository, human inputs, other EIP capsules, and global Codex state.

## Acceptance criteria

- Every approved Amsterdam EIP has an explicit included or excluded inventory record.
- Every included EIP has a verified substantive human assessment event and exact source blob.
- Every included EIP has a verified historical checklist or an explicit unresolved/divergent classification.
- Every automated run reuses the exact approved Task 04 EIP blob and Task 05 supporting-document blobs.
- Human results are inaccessible to assessors until automated results are validated and frozen.
- One fresh gpt-5.6-sol xhigh isolated session produces each historical-checklist result.
- All outputs and comparisons pass mechanical validation.
- Clean and confounded comparisons are reported separately.
- Historical-checklist results remain outside primary Task 05 outputs and fork totals.
- No Task 04 ref, Task 05 package, Task 05 result, or PM source is modified.
- Work is committed locally in task-owned paths only; nothing is pushed.

## Stop conditions

Stop and report rather than infer when:

- local Git history is incomplete for a selected human event or EIP state;
- a human score cannot be reconstructed without assuming blank values;
- a historical rubric cannot be matched to the human file;
- an automated capsule contains human or current-assessment material;
- isolation or network denial cannot be demonstrated;
- an existing canonical output would be overwritten;
- validation would require changing an assessor's score or rationale; or
- unrelated dirty work overlaps the task-owned directory.

