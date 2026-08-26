# Historical execution-spec and test evidence feasibility

## Recommendation

Keep EIP-only Task 05 assessments as the primary retrospective baseline. Do not add `execution-specs` or `execution-spec-tests` material to primary sealed packages.

Permit, after explicit project-owner approval, one artifact-assisted sensitivity run for Amsterdam EIP-8282 using a deterministic excerpt or a minimal exact-blob allowlist derived from the 17 historical blobs in its Task 04c record. Preserve that result separately from the original EIP-only assessment and do not mix it into primary cross-fork totals.

No repository–EIP pair qualifies as `primary_candidate`. Of 98 repository–EIP judgments, 91 are `exclude`, six are `provenance_only`, and one is `supplementary_candidate`. The source coverage is therefore too sparse and uneven to support a cross-fork primary-evidence policy.

## Scope and method

The study covers all 49 execution-affecting EIPs with approved Task 04 records: five Shanghai, six Cancun, eleven Prague, twelve Osaka, and fifteen Amsterdam records. Each record is evaluated independently against both `ethereum/execution-specs` and `ethereum/execution-spec-tests`, producing 98 repository–EIP judgments.

Each snapshot uses the exact Task 04 `selection.information_cutoff_at` and Git committer time. Date-only cutoffs are normalized to `00:00:00Z`, consistent with Task 04's day-precision boundary. Snapshot resolution follows the first-parent upstream default-branch lineage. This restriction matters because EELS imported EEST history as merge parents in 2025; unrestricted reachability can return an EEST-side commit that existed at the date but was not the EELS default-branch repository state.

The search covered the complete historical tree, exact-number path and content patterns, reachable commit subjects, and defensible fork-specific paths discovered from contemporaneous commits. Every positive claim is tied to the resolved snapshot, full Git blob SHA, SHA-256, last-change provenance, and immutable GitHub URL. Every negative record preserves the tree boundary, patterns, hits, rejected hits, and naming uncertainty.

No internet source, current working-tree content, client implementation, external fixture release, Hive checkout, or generated fixture was used in a maturity judgment.

## Repository preflight

Both local clones contain complete, connected history through the earliest required cutoff of 2022-02-04. Neither is shallow or partial, neither reports missing reachable objects, both use SHA-1 objects, and both pass `git fsck --connectivity-only --no-dangling`.

| Repository | Local path | Origin | Default-branch lineage | Recorded HEAD | First-parent root |
| --- | --- | --- | --- | --- | --- |
| `ethereum/execution-specs` | `/home/dtopz/code/github/execution-specs` | `git@github.com:ethereum/execution-specs.git` | `origin/forks/amsterdam` | `2ce2191562f76ec6e64a82f82165d821e1c781fc` | `1d1ce95f5f5dc8371a5d0d43b2c08c91eb9c61c9`, 2020-08-11 |
| `ethereum/execution-spec-tests` | `/home/dtopz/code/github/execution-spec-tests` | `git@github.com:ethereum/execution-spec-tests` | `origin/main` | `10eaa63d5da2f50b63d4359968f36542212f9f50` | `99bfc0b30f2fd235ffa349606605ce9a9683c6fb`, 2021-10-13 |

The exact remotes, clone properties, object checks, and root timestamps are in [`repositories.yaml`](repositories.yaml).

## EEST-to-EELS migration chronology

The local histories do not support one single “merge date.” They show a staged weld:

1. EELS commit `0bcb94511009d5f07ca805d2a44b3a97b08edaca` added EEST as the `eest_tests/execution-spec-tests` submodule on 2025-07-24, pointing to EEST commit `6cf5107cee0eae1c2d4dd6a5ef5bc729aea6c379`.
2. EELS merge commit `4d94a805d7a4c76a5945458922a6e2a0d868ddb0` imported EEST test sources under `tests/eest` as a Git subtree on 2025-08-25, from subtree split `e1e722807359ac01dc22c3d23e5de36ec675b3b1`.
3. EELS commit `1e7a52c9fb46e391090d4ee55fe3024b7f6e88ef` removed the submodule immediately after the subtree import on 2025-08-25.
4. EELS commit `9edc7d5ad795e9708ac985839e9c92de8fc30dee` moved EEST sources into their EELS package on 2025-10-16, and commit `2648ffcda8d32cf38c22943d50e325edcb34e504` moved `tests/eest` to the top-level `tests` directory on 2025-10-21.
5. EEST commit `e9958ed222364f27c4171128263c3ff5df7eb38d` recorded weld finalization and disabled CI on 2025-11-06; its README states that the repository stopped accepting pull requests effective 2025-11-01.
6. EEST commit `10eaa63d5da2f50b63d4359968f36542212f9f50` reduced the README to fully archived status on 2026-07-02.

The user's recollection of a merge around Osaka is directionally consistent with this staged 2025 weld, but the candidate repository histories do not themselves establish the Osaka activation date. The evidence policy should use the concrete repository phases above rather than an activation-relative shorthand.

## Cross-fork results

Counts below treat each repository–EIP pair as one judgment.

| Fork | EIPs | Absent | Reference only | Partial | Substantively informative | Exclude | Provenance only | Supplementary candidate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Shanghai | 5 | 10 | 0 | 0 | 0 | 10 | 0 | 0 |
| Cancun | 6 | 10 | 2 | 0 | 0 | 10 | 2 | 0 |
| Prague | 11 | 21 | 1 | 0 | 0 | 21 | 1 | 0 |
| Osaka | 12 | 22 | 0 | 2 | 0 | 22 | 2 | 0 |
| Amsterdam | 15 | 28 | 0 | 0 | 2 | 28 | 1 | 1 |
| Total | 49 | 91 | 3 | 2 | 2 | 91 | 6 | 1 |

No pair is classified as `scaffold`, `uncertain`, `uncertainty_context`, or `primary_candidate`. Exact counts and EIP inventories are under [`outputs/forks/`](forks/).

### Shanghai

The Shanghai hypothesis is confirmed directly: the original EEST repository existed, but it had no EIP-specific material at any of the five approved cutoffs. EELS also had no qualifying behavior, test, scaffold, or EIP-specific configuration. Repository existence therefore adds no assessment evidence for Shanghai.

### Cancun

The Cancun EELS maturity hypothesis is also confirmed directly. At the six approved cutoffs, EELS has only legacy upgrade-tracker references for EIP-1153 and EIP-4844; neither is executable specification behavior or test evidence. The other ten repository–EIP pairs are absent. EEST has no qualifying Cancun evidence at any approved cutoff.

This result is especially important because present-day Cancun support in both projects would make a current-tree inspection look highly informative. That maturity arrived after the proposal-time boundaries and cannot be back-projected.

### Prague

Twenty-one of 22 repository–EIP pairs are absent. The sole positive is EELS reference-only material for EIP-2537 in old YOLOv2 and Berlin documents. One file is explicitly retrospective, so it is hindsight-bearing and provenance-only. Prague does not supply a usable middle-period bridge between the sparse earlier forks and later repository maturity.

### Osaka

EEST has material source tests for only EIP-7939 and EIP-7951 at their cutoffs. Both suites are technically meaningful but version-provenance defective:

- The EIP-7939 suite declares `REFERENCE_SPEC_VERSION` `c8321494fdfbfda52ad46c3515a7ca5dc86b857c`; the local EIPs object database maps that blob to `EIPS/eip-7823.md`, not EIP-7939. The approved EIP-7939 blob is `1a4aed0bca3a74bc2caa37c16514098e3d072a8c`.
- The EIP-7951 suite declares `REFERENCE_SPEC_VERSION` `06aadd458ee04ede80498db55927b052eb5bef38`; the local EIPs object database maps that blob to `EIPS/eip-2935.md`, not EIP-7951. The approved EIP-7951 blob is `f4600e688beaeaf11fa6292ea3477e9ca3febe56`.

The EIP-7951 tests also predate the selected EIP creation commit. They may reflect a real pre-publication design, but the default-branch snapshot does not identify an admissible historical proposal source for that design. Both suites are `partial` and `provenance_only`: they document work underway, but should not affect Task 05 criterion scores or assessor confidence.

The other 22 Osaka repository–EIP pairs are absent. This sparse and defective availability is not sufficient for a consistent Osaka sensitivity policy.

### Amsterdam

Two EELS cases are substantively informative:

- EIP-7610 has executable specification behavior originating in commit `f5c433c44e50bf3b3c063077e725efb3e9ef83fa` on 2024-12-20, roughly nine months before its Amsterdam proposal cutoff. The code exposes a storage predicate and both opcode-level and transaction-level creation collision paths. It adds material information, but primarily reveals a finished solution and repository-wide porting work. It is `provenance_only`.
- EIP-8282 has executable specification behavior, test-fork configuration, contract artifacts, and extensive behavioral tests before its 2026-07-13 cutoff. Its test suite pins blob `35ab20cb31a416c50600da00125d262e1756850c`, exactly matching the approved Task 04 EIP blob. It is the only `supplementary_candidate`.

The remaining 28 Amsterdam repository–EIP pairs are absent. Even after the weld, repository evidence is not consistently available at proposal cutoffs.

## Methodological assessment

### Implementation-like specification code

Executable specification code reveals a solution that has already been designed, decomposed, and often debugged. This can lower perceived uncertainty, reveal the number of touched components, and make an implementation look easier because the reviewer sees working pseudocode or Python. That is useful for observed-development research, but it changes a proposal-time complexity assessment into a proposal-plus-realized-solution assessment.

EIP-7610 demonstrates this risk cleanly: the historical code is contemporaneous with the later cutoff, yet it predates the proposal event by months and exposes completed cross-module work. Historical availability alone does not make it methodologically admissible.

### Tests and design decisions

Tests can clarify boundary cases, transition behavior, failure modes, and integration points that an EIP already specifies. They can also encode decisions that the selected EIP had not yet made or bind to a different draft. The Osaka checksum defects and the pre-creation EIP-7951 tests show why exact version binding is required before treating tests as proposal evidence.

The EIP-8282 suite is safer because it binds exactly to the approved EIP blob. It still exposes completed work, so it is suitable only for sensitivity analysis, not the primary assignment.

### Cross-fork comparability

Artifact availability rises sharply over time: none for Shanghai, only reference documents for Cancun and Prague, two defective suites for Osaka, and two informative EELS cases for Amsterdam. Adding artifacts opportunistically would give later EIPs more detailed implementation and test context, bias confidence and potentially scores, and make fork totals incomparable.

The weld compounds this asymmetry. Before the weld, EELS and EEST are distinct evidence channels. During the transition, EELS can contain subtree copies while EEST remains active. After 2025-11-01, EELS is the canonical contribution repository and EEST is archival. A policy that simply searches both present repositories would double-count migrated material and conceal which repository actually carried it at the cutoff.

### Scores, confidence, and under-specification

Supporting repository artifacts should not alter scores, confidence, or under-specification in the primary EIP-only assessments. Primary confidence should continue to reflect the selected EIP package, not external evidence that other EIPs and forks did not have.

Task 04c maturity findings may be reported as research-level annotations alongside later analysis. A separately sealed sensitivity assessment may assign its own scores, confidence, and under-specification using an approved artifact package, but it must remain paired with and subordinate to the original EIP-only result.

### Policy before and after the weld

Before the 2025-08-25 subtree import, inspect EELS and EEST independently. From the subtree import through the 2025-10-21 path move, track origin and path explicitly and do not count a copied EEST artifact as independent EELS corroboration. From the 2025-11-01 contributor cutover onward, treat EELS as the canonical candidate and EEST as archival provenance unless a cutoff-specific EEST commit independently contains unique material.

The admissibility standard does not become looser after the weld. Exact cutoff, exact EIP binding, material information gain, and construct-validity review remain mandatory.

## Evidence exposure policy

Never provide an assessor with a repository checkout. The primary Task 05 package should remain EIP-only, with its existing directly required supporting-document rules.

For an approved EIP-8282 sensitivity run, prefer a deterministic excerpt over all 17 full blobs. The excerpt should contain:

1. The exact `spec.py` constants and its matching EIP blob binding.
2. Only the EIP-8282 request definitions and fork-processing entry points from `requests.py` and `fork.py`.
3. A deterministic inventory of test function names, parameter classes, and concise docstrings covering valid, invalid, fee, disable/reset, transition, out-of-gas, deployment, and mainnet cases.

The excerpt generator must record each source snapshot, path, Git blob SHA, source line selection, excerpt SHA-256, and generation command. If deterministic extraction is not implemented, use the exact 17-blob allowlist in [`amsterdam/eip-8282.yaml`](fork-eips/amsterdam/eip-8282.yaml), not a checkout or directory glob.

## Decision

The evidence policy recommended for Task 05 is:

- Primary assessments remain EIP-only.
- No artifact is promoted to primary evidence.
- EIP-8282 may receive one separately approved artifact-assisted sensitivity run.
- EIP-7610, the two Osaka suites, and the three reference-only cases remain provenance-only.
- All absent cases remain excluded; later content must not be substituted.
- Sensitivity results must preserve the original scores, use separate output paths, and remain excluded from primary cross-fork totals.

This policy answers the feasibility question without changing any existing Task 04 or Task 05 record.

## Limitations

- The search covers upstream default-branch history. It cannot rule out unmerged branches, private drafts, deleted remote refs, or pre-number work that left no trace in the cutoff tree.
- Local Git proves object, tree, and default-branch chronology. It does not independently archive GitHub visibility timestamps; public presence is inferred from inclusion in the upstream default-branch lineage at or before the cutoff.
- No internet lookup was needed. External announcements and activation dates were not used.
- The study evaluates evidence availability and admissibility, not whether an artifact-assisted assessor would actually change a score. That causal question belongs to the proposed EIP-8282 sensitivity run.
