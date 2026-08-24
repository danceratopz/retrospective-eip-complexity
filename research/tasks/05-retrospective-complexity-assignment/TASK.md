# Task 05: Perform one retrospective EIP complexity assignment

## Objective

Apply the pinned current complexity rubric to one exact historical EIP revision approved by Task 04. Exercise expert technical judgement, but evaluate only what was reasonably specified at the recorded information cutoff. The result must reflect the proposal as it appeared when it entered fork development, not the implementation that eventually shipped.

This task scores one EIP. It does not select the historical ref, reconstruct later development, compare predictions with outcomes, or calibrate the rubric.

## Execution boundary

- Run exactly one EIP in each fresh session.
- Use `gpt-5.6-sol` with `reasoning_effort: xhigh`.
- Run through the Task 05 isolated launcher. The assessor's working directory is the one-EIP capsule mounted at `/mnt/workspace`, never the project repository.
- Read only this contract, `PROMPT.md`, and files inside `package/`.
- Write only `/mnt/workspace/assessment.yaml`. The trusted launcher validates, imports, and marks completion after the assessor process exits.
- Do not attempt to locate the project repository, vault, another EIP's package, or another assessment.
- Do not delegate any part of the assessment to another agent.

The assessor should reason as an expert human reviewer would. The rubric is a structured aid, not a keyword-matching exercise. A score must follow from the historical proposal's technical consequences and the relevant anchor definition.

## Required inputs

The isolated capsule presents one package as:

```text
package/
├── manifest.yaml
├── eip.md
├── rubric.md
├── output-template.yaml
└── supporting/
```

`manifest.yaml` is authoritative for the historical revision, information cutoff, rubric identity, supporting-document allowlist, and file hashes. `eip.md` is the exact selected Git blob. `rubric.md` is the hindsight-safe assessor view mechanically derived from the pinned rubric. Supporting files are included only when they were directly linked or required by the selected EIP and were pinned no later than the cutoff.

Do not follow links from these files. A visible URL is evidence recorded in the historical document, not permission to browse it.

## Hindsight firewall

The following sources and actions are prohibited:

- any internet access, including web search, browsers, networked shell commands, remote APIs, apps, plugins, or MCP servers;
- present-day or later versions of the EIP;
- Task 01, Task 03, or Task 04 research records beyond the sealed manifest;
- later bracketing revisions and diffs;
- current or historical client implementations unless included in the sealed package;
- execution-specs, execution-spec-tests, Hive tests, devnet records, fork outcomes, bugs, or observed implementation effort;
- existing complexity assessments, calibration reports, other EIP scores, or verifier reports;
- any generic implementation-oriented EIP assessment skill or command;
- opening or searching project-management records outside the sealed package.

Do not use a dedicated assessment skill. The isolated launcher disables skills and all external-information capabilities. Any attempted internet access, or any exposure to an internet-derived result, makes the run contaminated.

If prohibited information is exposed before the output is complete, stop. Write an output with `hindsight_control.contaminated: true`, describe the exposure, do not assign authoritative scores, and let the trusted launcher reject it.

## Assessment method

1. Verify the identities in `manifest.yaml` and `output-template.yaml` match the assigned fork and EIP.
2. Read `rubric.md` completely before scoring.
3. Read the historical EIP and every packaged supporting document completely.
4. Summarize the proposal's assessment-time scope in two to five sentences. Do not add later design knowledge.
5. Apply all 28 criteria in rubric order, including criteria scored zero.
6. For each criterion record:
   - one integer score permitted by the rubric;
   - one or more structured evidence entries in this exact shape:

     ```yaml
     evidence:
     - source: eip.md
       locator: Specification, lines 41-58
       summary: Concise description of what the cited passage establishes.
     ```

   - a concise technical rationale tied to the anchor definition;
   - confidence (`high`, `medium`, or `low`); and
   - an uncertainty note, using `None identified.` when there is no material uncertainty.
7. Use score 4 only in the rubric's exceptional circumstances and provide a separate justification. `Cross-EIP interactions` remains uncapped and must list identified interacting EIPs as bare YAML integers, for example `interacting_eips: [5793]`. If the historical package describes an interaction but provides no EIP number, do not infer it from later knowledge; use `unidentified_interactions` for a concise package-grounded description. Use both lists as `[]` when the score is zero.
8. Calculate the total as the exact sum of criterion scores and apply the rubric tier thresholds mechanically.
9. Record under-specification separately from primary scoring.
10. Complete the provenance and hindsight-control attestations. Preserve the launcher-populated `session_id`, `session_id_source`, and `isolation_method` exactly.

Preserve the pre-populated `sources_consulted` and `operational_files_read` lists exactly. `sources_consulted` contains only admissible assessment evidence (`eip.md`, `rubric.md`, and any allowlisted supporting documents). The operational list separately records the task, prompt, manifest, and output template; operational files must never be cited as scoring evidence.

## Under-specification

Judge the EIP as written. Do not repair gaps from memory and do not assume the final design.

Under-specification is scored directly only where a rubric criterion calls for it, especially `Unspecified behavior requiring cross-client consensus`. For other affected criteria, choose the best-supported primary score from the available text, lower confidence as appropriate, and record a plausible score range. Do not convert the same missing detail into high scores across multiple criteria.

The structured under-specification section must state:

- whether material under-specification is present;
- the missing or unresolved behavior;
- affected criterion IDs;
- a plausible total-score range containing the primary total;
- every tier reachable within that range; and
- unresolved interpretation questions.

## Evidence standard

Use only package-relative paths. Prefer a Markdown heading plus a line range, for example `eip.md: Specification, lines 41-58`. Evidence may summarize the relevant text; long quotations are unnecessary. A zero score still needs a locator and rationale explaining why the proposal does not trigger that criterion.

## Output

Copy `package/output-template.yaml` to:

```text
/mnt/workspace/assessment.yaml
```

Fill every null or placeholder required by the template. Preserve mechanically populated provenance values exactly. The original assessment must remain visible in later verification work and must never be silently overwritten by a verifier.

Do not run repository validators, copy the result elsewhere, or touch a shared checklist. After the session exits, the trusted launcher validates the capsule output against the canonical sealed package, copies it without overwriting any existing result, and mechanically ticks only this EIP in the shared completion checklist.

## Completion conditions

The EIP is complete only when:

- all 28 criteria are present once in canonical order;
- every score has evidence, rationale, confidence, and an uncertainty note;
- total and tier are mechanically correct;
- provenance identifies the sealed package, prompt, model, reasoning effort, isolated launcher session, and rubric;
- the hindsight attestation is complete and the run is not contaminated;
- the trusted launcher accepts and imports the output; and
- the Osaka completion checkbox is ticked by the trusted launcher.
