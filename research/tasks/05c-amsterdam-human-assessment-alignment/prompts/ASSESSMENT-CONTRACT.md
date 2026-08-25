# Historical-checklist assessment contract

Assess exactly the one proposal in `package/` using only the historical checklist in `package/rubric.md`.

Your readable assessment evidence is positively limited to the paths listed by `assessment_source_files` in `package/manifest.yaml`. `PROMPT.md`, this contract, the manifest, and the output template are operational files, not scoring evidence. Read the rubric, EIP, and every allowlisted supporting file completely. Do not follow links; visible URLs are provenance only.

Apply all historical checklist rows in their exact order, including rows scored zero. Use only a score listed for that row in the output template. A score of 4 requires an exceptional-score justification because the historical rubric permits it only for exceptional complexity or impact. The historical checklist's `Engine API encoding changes` row has no dedicated definition in the source template; do not invent one or import a definition from another rubric. Score it conservatively from the row label and global score range, lower confidence, and record the missing definition as uncertainty.

Ground every score in one or more package-relative evidence entries with `source`, `locator`, and `summary`. Give a concise rationale, confidence (`low`, `medium`, or `high`), and an uncertainty note for every row. Record material under-specification separately; do not multiply one missing detail across unrelated rows. Calculate the total and tier mechanically from the historical thresholds in the template.

The internet, web search, browsers, network commands, apps, plugins, MCP servers, skills, project-management records, human assessments, calibration data, current-rubric scores, other EIP packages, later EIP revisions, implementations, tests, devnets, and fork outcomes are prohibited. Do not search for a hidden repository or use latent knowledge as evidence. Latent model knowledge cannot be removed; rely only on the package and attest to that boundary.

If prohibited information is exposed before completion, set `hindsight_control.contaminated: true`, describe the exposure, do not provide an authoritative result, and stop. Otherwise copy `package/output-template.yaml` to `assessment.yaml`, fill every placeholder, preserve all pre-populated provenance and lists exactly, and write no other file.
