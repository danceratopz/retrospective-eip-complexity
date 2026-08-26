# Hegotá snapshot assessment contract

Assess exactly the one proposal in `package/` using only the checklist in `package/rubric.md` and the common snapshot recorded in `package/manifest.yaml`.

Readable assessment evidence is positively limited to the paths listed under `assessment_source_files`. `PROMPT.md`, this contract, the manifest, and the output template are operational files, not scoring evidence. Read the rubric, EIP, and every allowlisted supporting file completely. Do not follow links; visible URLs are provenance only.

Apply all 28 checklist rows in exact order, including rows scored zero. Use only a score permitted by that row. A score of 4 requires the rubric's exceptional-impact justification. `Cross-EIP interactions` remains uncapped; identified interacting EIPs must be bare integers, while package-grounded interactions without a known EIP number belong in `unidentified_interactions`.

Ground every score in one or more evidence entries containing `source`, `locator`, and `summary`. Give a concise rationale, confidence (`low`, `medium`, or `high`), and uncertainty note for every row. Record material under-specification separately. Do not fill gaps from memory, assume the final design, or spread one ambiguity across unrelated rows.

Assess execution-layer complexity only. The coordinator has admitted this package because the proposal has an execution-layer or execution-client networking surface. For a cross-layer EIP, do not assign complexity solely for consensus-layer behavior; record the boundary and any resulting uncertainty.

The internet, browsers, network commands, apps, plugins, MCP servers, skills, repositories, project-management records, other packages, existing complexity assessments, calibration data, later revisions, implementations, tests, devnets, client discussions, fork decisions, and outcomes are prohibited. Do not search for hidden files or use latent knowledge as evidence.

If prohibited information is exposed before completion, set `information_control.contaminated: true`, describe the exposure, do not provide an authoritative result, and stop. Otherwise copy `package/output-template.yaml` to `assessment.yaml`, fill every placeholder, preserve all pre-populated provenance and lists exactly, and write no other file.
