# Amsterdam historical-checklist alignment summary

This calibration study compares a newly blinded historical-checklist automated assessment (B) with the published historical human assessment (C). The existing checklist-revision-2 automated result (A) is included only for controlled rubric sensitivity on the same Task 04 input. Task 05c scores are not primary fork scores.

## Population

The mechanically derived population contains 12 included EIPs from 15 approved Amsterdam refs. 3 were excluded: EIP-7954 (no_historical_human_assessment); EIP-8246 (no_historical_human_assessment); EIP-8282 (no_historical_human_assessment).

Only 2 comparisons meet the predeclared clean-input/template/total conditions; 10 are descriptive confounded comparisons. 1 clean comparison also has low classified hindsight exposure.

## Human–automated alignment (B versus C)

| Subset | N | Exact total agreement | Mean absolute error | Median absolute error | Signed bias (B-C) | Spearman | Kendall tau-b | Tier agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| All reconstructable | 12 | 0.0 | 5.3333 | 5.0 | 2.8333 | 0.6078 | 0.4286 | 0.1667 |
| Clean | 2 | 0.0 | 7 | 7.0 | 7 | -1.0 | -1.0 | 0.0 |

The clean subset has only two records; its rank correlations are arithmetic outputs and are not substantively interpretable.

Clean tier confusion (rows are human, columns automated):

| Human \ Automated | Low | Medium | High |
|---|---:|---:|---:|
| Low | 0 | 2 | 0 |
| Medium | 0 | 0 | 0 |
| High | 0 | 0 | 0 |

Per-anchor differences are stored in every comparison record. Aggregate all-row per-anchor means:

| Historical anchor | N | Mean signed B-C | Mean absolute difference |
|---|---:|---:|---:|
| EVM Gas rule changes | 12 | -0.9167 | 1.25 |
| Blob gas accounting changes | 12 | -0.0833 | 0.0833 |
| New EVM gas refund | 12 | -0.25 | 0.25 |
| Patterns affecting pre-existing tests | 12 | -0.3333 | 1.1667 |
| Transition-tool interface changes | 12 | -0.0833 | 0.4167 |
| Cryptography-related testing | 12 | 0 | 0 |
| Edge/boundary conditions | 12 | 0.5 | 0.6667 |
| Block syncing changes | 12 | 0.1667 | 0.1667 |
| Engine API changes | 12 | -0.25 | 0.25 |
| Engine API encoding changes | 12 | 0.0833 | 0.0833 |
| Added system contracts | 12 | -0.0833 | 0.0833 |
| Modified system contracts | 12 | -0.25 | 0.25 |
| Added opcodes | 12 | 0 | 0 |
| Modified opcodes | 12 | 0.1667 | 0.6667 |
| Added precompiles | 12 | 0 | 0 |
| Modified precompiles | 12 | 0 | 0 |
| Encoding changes (RLP/SSZ) | 12 | 0.5 | 0.5 |
| New transaction types | 12 | 0 | 0 |
| New or modified transaction validity mechanisms | 12 | -0.4167 | 0.5833 |
| New block / header fields | 12 | 0 | 0 |
| New fork activation mechanism | 12 | 0.4167 | 0.4167 |
| Performance risks | 12 | 1 | 1 |
| Security risks | 12 | 1.5 | 1.8333 |
| Cross-EIP interactions | 12 | 1.1667 | 1.1667 |

## Confounds

Substantive or unknown EIP-input drift affects 9 records: EIP-2780, EIP-7610, EIP-7778, EIP-7928, EIP-7981, EIP-7997, EIP-8024, EIP-8037, EIP-8038. These rows are excluded from the clean aggregate even though they remain in the descriptive dataset.

Human timing exposure counts: high_exposure=5, low_exposure=4, possible_exposure=3. Exposure is reported separately and does not retroactively alter the historical record.

## Rubric revision effect (A versus B)

Across 12 same-input automated pairs, mean A-minus-B is 4.1667, median is 3.5, and the range is -2 to 14. A uses 28 rows, revision-2 thresholds (<12, 12–22, >=23), and an uncapped Cross-EIP row; B uses 24 rows, a nominal maximum of 72, and historical thresholds (<10, 10–19, >=20). The delta is therefore descriptive sensitivity, not a common-scale causal estimate.

## Qualitative examples

The smallest observed total difference is EIP-7778 (B=8, C=10, absolute error=2).

The largest material disagreement is EIP-7843 (B=17, C=7, absolute error=10); interpret it with its recorded input-alignment, template-match, and timing-exposure classifications rather than as a pure evaluator error.

## Limitations

The Amsterdam sample is small, and the clean subset is smaller still, so rank statistics and percentages are unstable descriptions rather than decisive estimates. Amsterdam evidence contributed to later checklist work, making the fork in-sample for revision 2 even though the B runs were blinded. Human reviews sometimes used implementation or test knowledge and often saw later EIP states. Model latent knowledge cannot be removed; package-grounded evidence and isolation reduce observable hindsight channels but cannot erase learned background knowledge. No rubric weights were optimized, no p-values are used, and no causal claim is made.
