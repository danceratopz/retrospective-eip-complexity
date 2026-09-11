# Static publication contract

Status: `public`. The owner authorized deployment of the sanitized static artifact to `https://danceratopz.github.io/retrospective-eip-complexity/` on 27 August 2026.

## Normative scope

This directory owns the approved static-publication boundary, deterministic adapter, and Astro site. The research tasks remain authoritative and read-only; generated publication data and the built artifact are reproducible, ignored products.

The research method remains defined by the repository's [README](../README.md), [data and provenance policy](../DATA.md), [reproduction guide](../REPRODUCING.md), and [research task map](../research/README.md). This contract does not restate their full methodology. A future adapter carries the concise reader-facing method summary in `study_metadata.payload.public_summary`, while the source record and hash retain the link to the canonical document.

The following decisions are fixed:

- Astro 7.2.7 on Node 22.22.1 is the selected static site shell. No UI framework, server adapter, database, analytics, telemetry, or client-side application state is approved.
- Python/YAML research outputs remain authoritative and read-only.
- A one-way Python adapter will emit sanitized, schema-versioned JSON and CSV.
- Vega-Lite 6.4.1 remains the visualization grammar, with Vega 6.4.0 and Vega-Embed 7.1.0 bundled as one local runtime.
- The site explains method before results and supports both fork and EIP browsing.
- Retrospective and prospective records remain structurally separate.
- A minimal project-owned Python generator is a fallback only if the owner later rejects Node/npm or limits the site to a fixed snapshot.
- Deployment uses a clean-checkout custom GitHub Actions Pages artifact, full-SHA action pins, and least privileges.
- Only the adapter’s sanitized output is deployed; canonical research inputs remain repository records and excluded operational material is never copied into the Pages artifact.

Changing one of these decisions requires an explicit owner review and a versioned contract change. An implementation inconsistency is a reason to stop, not permission to select another architecture silently.

## Four-layer architecture

1. **Canonical research.** Task-owned YAML, approved records, frozen assessments, source registries, and approved derived analyses are the source of truth. Publication work reads them without invoking a writer or mutating an output tree.
2. **Publication adapter.** A future project-owned Python adapter reads only the roots and record classes in [`contract/adapter-boundary.json`](contract/adapter-boundary.json). It denies every unlisted input, projects affirmative public fields, attaches source paths and hashes, and emits stable JSON/CSV into a separate ignored staging directory.
3. **Vega-Lite visualization.** Approved specifications and sanitized data remain declarative. The future shared runtime renders them locally, while prose and semantic tables preserve the result without JavaScript.
4. **Astro site shell.** Astro owns static routes, navigation, templates, labels, prose, base-path-aware links, accessible tables, and local assets. It does not calculate scores or alter research records.

Data flows only in that order. No site edit can flow back into a research task, and a derived publication record never becomes canonical merely because it is easier to consume.

## Audiences and reading order

The site serves Ethereum protocol contributors, client and test implementers, research-method reviewers, and reproducibility or source auditors. It must let a new reader establish the question, study scope, evidence controls, scoring rubric, maturity, and limitations before seeing comparison results.

The required order is:

1. research question and five-fork retrospective scope;
2. workflow, evidence freezing, historical cutoffs, scope classifications, and EL-rubric boundary;
3. status vocabulary, canonical/derived ownership, observed-effort proxy construction, and limitations;
4. fork and EIP browsing with criterion evidence and provenance;
5. fork-level predicted complexity, association results, and the limited Amsterdam human–LLM comparison; and
6. approved downloadable data products.

The landing page must not lead with a correlation coefficient. Scores and associations appear only where method and caveats are available through the required cross-links in [`contract/routes.json`](contract/routes.json).

## Route and template contract

Route identity, path parameters, source record types, templates, labels, provenance requirements, navigation, release states, and allowed cross-links are machine-owned by [`contract/routes.json`](contract/routes.json). The global navigation is Study, Forks, EIPs, Results, and Human vs LLM.

The required route families are:

| Area | Routes | Reader-facing authority |
| --- | --- | --- |
| Landing | `/` | Question, study scope, current maturity, caveats, and reading path |
| Study | `/study/` | Background, research question, scope, method, evidence controls, scoring rubric, design decisions, and limitations |
| Forks | `/forks/`, `/forks/{fork}/` | Fork inventory, maturity, timeline, scope, totals, EIPs, and caveats |
| EIPs | `/eips/`, `/eips/{eip}/` | Global occurrence index; never a collapsed cross-cutoff score |
| Assessments | `/forks/{fork}/eips/{eip}/` | The scoring authority shown to readers for one fork cutoff and EIP revision |
| Results | `/results/predicted-vs-observed/` | Fork complexity totals, shipping-time comparisons, observed-effort associations, mandatory caveats, and semantic tables |
| Human vs LLM | `/human-vs-llm/` | Descriptive Amsterdam comparison of published human and blinded LLM complexity evaluations |
| Prospective | `/prospective/hegota/` | Approved frozen Task 08 summary, plot, semantic table, downloads, provenance, and caveats |

Approved downloads remain linked from the relevant results and assessment pages. Canonical research records and reproduction instructions remain repository documentation rather than standalone publication routes.

One EIP may have different assessment refs and information cutoffs in different forks. The fork-specific assessment page is therefore the reader-facing score authority. A global EIP page may aggregate occurrences and cross-links, but it must never replace distinct fork cutoffs with one score.

The Hegotá route accepts the owner-approved `hegota-candidates-2026-08-26-ac450a4` combined view only: the unchanged 44-entry PFI freeze plus the append-only SFI/CFI extension from the same source snapshot. It contains 46 status-labelled entries, 39 validated assessments, 7 not-applicable dispositions, and an EL-rubric score sum of 856. The page must retain the original PFI subtotal of 776 across 37 assessments and identify EIP-7805 and EIP-8141 as Hegotá SFI'd/CFI'd EIPs at the time of the 2026-08-26 snapshot. `prospective_cohort_summary` owns the page and `prospective_eip_assessment` owns its table rows. These records remain structurally separate from Task 05 and never enter Task 07 correlations or observed-effort plots.

## Terminology and labels

Exact display text, applicability, minimum caveats, allowed chart/table treatments, mutual exclusions, and prohibited substitutions are machine-owned by [`contract/labels.json`](contract/labels.json).

- **Historical / retrospective** means an approved historical revision was evaluated at its recorded information cutoff, not that the final shipped specification was scored.
- **Prospective** means an evaluation against one pre-agreed snapshot before the observed outcome. It is mutually exclusive with retrospective.
- **Provisional** means the required human approval gate has not passed. All Task 04b classification state remains provisional until explicit approval.
- **Forecastable at cutoff** and **Late scope** are mutually exclusive Task 04b scope classifications. They do not change an individual EIP's Task 04 ref or transfer one EIP's score to another.
- **Censored** means an observation window is incomplete. **Right-censored** means it ends at a censor date before the final outcome; Amsterdam requires both the right-censored meaning and its pinned date wherever observed-effort values appear.
- **Potentially in-sample** means later Amsterdam evidence may have informed the rubric or study design. Amsterdam associations are not independent out-of-sample validation.
- **Not applicable to EL rubric** is the only scoring treatment for consensus-only work in this study. It is never an execution-layer score of zero.
- **Under-specified** means the historical text leaves material behavior unresolved. The visible assessment must preserve uncertainty, affected criteria, and the plausible range.
- **Canonical** means the originating research task owns the frozen input or approved result.
- **Derived** means the record is reproducible from named canonical sources but is not itself the source of truth.
- **Observed-effort proxy** means a descriptive metric derived from recorded public artifacts. It is not person-hours, engineering cost, or causal effort.

Labels are structured data, not prose decoration. The adapter fails if a mandatory label is absent, if mutually exclusive labels coexist, if consensus-only work receives a numeric EL score, if a proposed Task 04b cohort loses `provisional`, or if an Amsterdam observed-effort record loses `right_censored` or `potentially_in_sample` where its source requires them.

## Prohibited publication language

Publication prose, charts, captions, metadata, and table headings must not state or imply:

- that complexity caused observed effort, delay, defects, or cost;
- that an observed-effort proxy measures actual effort or person-hours;
- “prediction accuracy,” “calibrated prediction,” “validated forecast,” or equivalent performance claims from this retrospective association study;
- that the two clean Task 05c comparisons calibrate the rubric or model;
- that a consensus-only EIP has zero execution-layer complexity;
- that provisional Task 04b cohorts are approved or final;
- that Amsterdam is a complete outcome or independent out-of-sample validation; or
- that a global EIP has one score when fork-specific historical cutoffs differ.

Supported language is descriptive: association within five forks and 49 retrospective fork–EIP assessments, with explicit proxy, censoring, provisional-cohort, input-drift, and in-sample limitations.

## Publication record envelope

Every future sanitized record must validate against [`schemas/publication-record.schema.json`](schemas/publication-record.schema.json) and contain:

- schema version, known record type, stable ID, and base-aware route;
- the source Git commit;
- one or more repository-relative source records with SHA-256 and source-disposition identifiers;
- canonical or derived ownership and a known maturity;
- every required structured label;
- at least one visible limitation;
- provenance naming the source task, authoritative owner, derivation, and adapter contract;
- a public download disposition; and
- the payload selected by record type.

Fork–EIP assessment records additionally carry the exact assessment commit, EIP path, Git blob SHA, content SHA-256, and information cutoff. Public provenance contains repository-relative paths and public upstream URLs only. No future public record may expose absolute machine paths, temporary paths, local file URLs, assessor run identifiers, prompts, capsules, logs, credentials, tokens, operational metadata, raw source bodies without an affirmative body disposition, or incomplete prospective work.

The record types are study metadata, fork, global EIP, retrospective fork–EIP assessment, result summary, chart specification/data index, data catalog entry, prospective cohort summary, prospective EIP assessment, and the deprecated empty prospective status retained only for schema compatibility.

## Adapter and source boundary

[`contract/adapter-boundary.json`](contract/adapter-boundary.json) owns the future read-only interface, exact input roots, canonical and approved-derived classes, output types, identity fields, serialization rules, deny rules, build failures, and prospective gate. Anything not affirmatively listed is denied.

The public allowlist contains only authored publication prose, sanitized schema-versioned records, approved Vega-Lite specifications and chart data, approved static downloads, locally built assets, open-source notices, and a public provenance manifest. It never authorizes recursive copying of a research task directory.

The following remain excluded by default:

- all raw evidence trees and sealed packages as whole files;
- prompts, capsules, run records, logs, caches, scratchpads, and temporary packages;
- assessor identifiers and other operational metadata;
- absolute local or temporary paths and local file URLs;
- private, credential-bearing, or environment material;
- unapproved Task 04b presentation without a provisional state;
- all Task 08 packages, prompts, raw outputs, session metadata, working material, or partial results; only the explicitly allowlisted frozen outputs may be projected;
- source bodies with unknown or reference-only redistribution; and
- any field or asset not named by the allowlist.

[`contract/source-dispositions.json`](contract/source-dispositions.json) mechanically inventories the current Task 01 registry metadata without copying source bodies. Each source is keyed globally by work unit and registry ID. `unknown` redistribution is blocked. `not_applicable` permits metadata only. `reference_only` never permits a copied body. Although `allowed` sources may be cited as metadata, this contract approves no `public_body` entry; a later attribution review and explicit contract update are required. Blocked, excluded, or unknown identifiers fail a public build.

## Determinism, offline operation, accessibility, and responsive behavior

A future build must:

- run from a clean checkout against frozen, validated inputs without invoking research writers or network retrieval;
- use exact Python, Node, Astro, Vega, Vega-Lite, Vega-Embed, action, and dependency pins recorded in lockfiles or full SHAs;
- sort every collection and serialize UTF-8 JSON with two-space indentation, sorted keys, and one trailing newline;
- omit wall-clock build timestamps and use source-controlled identity such as the source commit when a date is needed;
- produce identical file lists and hashes on two consecutive builds from unchanged inputs;
- work beneath `/retrospective-eip-complexity/` with one centralized base-path helper;
- issue zero CDN, API, font, analytics, telemetry, or other external requests after build;
- keep one shared local visualization runtime rather than one inline runtime per chart;
- retain page title, method summary, status, limitations, semantic table, approved downloads, and provenance with JavaScript disabled; and
- fail closed on a missing input, unknown state, contradictory maturity, unsafe field, blocked source, broken internal link, or non-deterministic output.

Every page requires one `h1`, a descriptive title, skip link, landmark structure, visible focus, logical focus order, and keyboard-operable navigation. Every chart requires a concise visible interpretation, a programmatic description, and a semantic table or approved data download containing the plotted values. Color cannot be the sole state encoding, tooltips are supplementary, tables need captions and header scopes, sortable headers use buttons with `aria-sort`, form controls need labels, result counts use a polite live region, and reduced-motion and increased-contrast preferences are respected. SVG and untagged PDF may be convenience downloads but are never the accessible alternative.

Responsive acceptance covers 360, 768, 1,280, and 1,920 CSS pixels. At 360 pixels, navigation and prose must avoid page overflow; wide tables need a labelled overflow region or stacked alternative; dense timelines need a selector, small multiples, or an intentional scroll region with a visible cue; and the six-panel results dashboard must split into readable views. The later representative implementation must test current Chrome and Firefox automatically and include Safari, Edge, keyboard, screen-reader, 200% zoom, and contrast review.

Initial performance budgets are 200 KiB compressed for a non-chart route, no more than 500 KiB compressed shared visualization JavaScript on chart routes, and less than 2 MiB uncompressed page-specific chart/data payload. These budgets remain recommendations until the Amsterdam timeline and complete Task 07 table measure a representative implementation.

## Release states

The current state is `public`. [`contract/routes.json`](contract/routes.json) machine-owns the following transition conditions:

1. `contract_internal`: contract files may exist locally; nothing is published.
2. `local_preview`: a later Astro artifact is served only on localhost beneath the repository subpath.
3. `review_artifact`: a later non-public artifact is available only to designated reviewers and passes privacy scans.
4. `publication_ready`: every license, redistribution, data-freeze, privacy, accessibility, performance, and factual review gate passes.
5. `public`: the owner explicitly authorizes and creates the Pages deployment from the reviewed artifact.

Only the owner can authorize `publication_ready` or `public`. State transitions are monotonic review decisions, not values inferred from the presence of files. The owner explicitly authorized the Pages deployment represented by this contract revision on 27 August 2026.

## Public-release decision

The owner reviewed the static artifact and authorized its publication from `danceratopz/retrospective-eip-complexity`. The deployment preserves these release decisions:

- the repository currently grants no project license; default copyright applies;
- no upstream source body is republished, including sources with unknown or reference-only redistribution status;
- the validated 49-assessment Task 05 dataset is the retrospective publication snapshot;
- Task 04b classifications retain their provisional status and are not presented as approved findings;
- SVG and PDF downloads are not part of this release;
- automated privacy, link, accessibility-structure, determinism, and performance checks run before deployment; and
- the research limitations and prospective/retrospective separation remain visible in the artifact.

The validator passing proves internal consistency of this contract and artifact boundary. Public status records the owner’s deployment authorization; it is not a claim that the study’s stated methodological limitations have been eliminated.

## Machine-readable ownership

| Structured contract area | Owning file |
| --- | --- |
| Route families, parameters, templates, navigation, cross-links, provenance requirements, and release states | [`contract/routes.json`](contract/routes.json) |
| Exact display labels, definitions, applicability, caveats, treatments, exclusions, and substitutions | [`contract/labels.json`](contract/labels.json) |
| Allowed input roots/classes, output types, identity fields, serialization, allowlist, deny rules, build failures, and prospective gate | [`contract/adapter-boundary.json`](contract/adapter-boundary.json) |
| Per-source redistribution state, snapshot policy, proposed disposition, rationale, known notice, and blocker | [`contract/source-dispositions.json`](contract/source-dispositions.json) |
| Common record envelope and typed payloads | [`schemas/publication-record.schema.json`](schemas/publication-record.schema.json) |
| Positive and intentional negative examples | [`fixtures/publication-record.valid.json`](fixtures/publication-record.valid.json), [`fixtures/publication-record.invalid.json`](fixtures/publication-record.invalid.json) |
| Cross-file invariants, recursive safety rejection, fixture expectations, stable summary, and deny scan | [`scripts/validate_contract.py`](scripts/validate_contract.py) |

If prose and a machine-owned value conflict, implementation stops for contract review. It must not choose whichever value is easiest to render.
