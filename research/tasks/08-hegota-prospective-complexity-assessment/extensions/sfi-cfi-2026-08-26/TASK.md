# Task 08 extension: assess the Hegotá SFI'd and CFI'd EIPs

## Objective

Extend the frozen 2026-08-26 Hegotá study with EIP-7805, which EIP-8081 listed
as Scheduled for Inclusion, and EIP-8141, which it listed as Considered for
Inclusion. Evaluate them with the same execution-layer method as the 37 original
PFI assessments while leaving every original cohort, package, result, freeze,
and summary byte-for-byte unchanged.

Publish these records as **Hegotá SFI'd/CFI'd EIPs at the time of the
2026-08-26 snapshot**. Combined overview tables may place them alongside PFI
records only when each row visibly identifies its PFI, SFI, or CFI status.

## Frozen evidence and method

- EIPs commit: `ac450a4ab2f37387385ee9c54b62f518d97e6cc9`
- Information cutoff: `2026-08-25T11:56:58Z`
- Extension snapshot: `hegota-sfi-cfi-2026-08-26-ac450a4`
- Original PFI snapshot: `hegota-pfi-2026-08-26-ac450a4`
- Rubric commit: `3d8c0128c5543dd3146341ef395aa344e4abea30`
- Checklist revision: 2, using the byte-identical Task 05 assessor view
- Model: `gpt-5.6-sol`
- Reasoning effort: `xhigh`
- Isolation: one fresh bubblewrap capsule per EIP

The original Task 08 assessment contract, evidence policy, output schema,
28-criterion ordering, score rules, tier rules, and information firewall apply.
Consensus-spec, execution-specs, and execution-spec-tests links remain
provenance-only. Assessors must not use post-snapshot information, observed
outcomes, implementation evidence, prior scores, or the other extension result.

EIP-7805 is cross-layer. Its assessment covers only its execution-layer and
execution-client networking surface; consensus-layer complexity is explicitly
outside this rubric. EIP-8141 is evaluated as an execution-layer proposal.

## Append-only freeze order

1. Validate the two-entry extension manifest against the pinned EIP-8081.
2. Require both owner-approved layer dispositions.
3. Prove that the original 37 Task 08 and 49 Task 05 artifacts remain unchanged.
4. Build and validate two deterministic primary packages.
5. Freeze the package hashes and require byte-identical regeneration.
6. Run two fresh isolated assessors with no score or aggregate shared between them.
7. Validate and freeze both canonical assessments.
8. Render the extension summary and the combined 46-entry overview only after the freeze.

Never rewrite the original PFI manifests or summaries. The combined overview
must retain the original `776 across 37 PFI EIPs` subtotal separately from the
two-EIP extension and the 39-assessment combined view.
