# Hegotá candidate complexity at the 2026-08-26 snapshot

Original PFI result: **776 across 37 scored PFI EIPs**. SFI/CFI extension: **80 across 2 scored EIPs**. Combined visibility view: **856 across 39 scored EIPs**.

EIP-7805 and EIP-8141 are Hegotá SFI'd/CFI'd EIPs at the time of the 2026-08-26 snapshot; the status column distinguishes them from the original PFI cohort.

## Scored execution-layer surfaces

| EIP | Proposal | Snapshot status | Layers | Score | Tier | Confidence | Under-specified |
|---:|---|---|---|---:|---|---|---|
| EIP-2488 | Deprecate the CALLCODE opcode | PFI | execution | 10 | low | medium | yes |
| EIP-3298 | Remove storage-clear refund and refund cap | PFI | execution | 12 | medium | medium | no |
| EIP-4758 | Deactivate SELFDESTRUCT | PFI | execution | 14 | medium | medium | yes |
| EIP-5920 | PAY opcode | PFI | execution | 16 | medium | medium | yes |
| EIP-7645 | Alias ORIGIN to SENDER | PFI | execution | 11 | low | medium | yes |
| EIP-7666 | EVM-ify the identity precompile | PFI | execution | 15 | medium | medium | no |
| EIP-7668 | Remove bloom filters | PFI | execution | 10 | low | medium | yes |
| EIP-7709 | Read BLOCKHASH from Storage and Update Cost | PFI | execution | 20 | medium | medium | yes |
| EIP-7805 | Fork-choice enforced Inclusion Lists (FOCIL) | SFI | execution, consensus | 20 | medium | medium | yes |
| EIP-7807 | SSZ execution blocks | PFI | execution, consensus | 34 | high | medium | yes |
| EIP-7819 | SETDELEGATE instruction | PFI | execution | 21 | medium | medium | yes |
| EIP-7851 | Code-Controlled EOA Delegation | PFI | execution | 23 | high | medium | yes |
| EIP-7862 | Delayed State Root | PFI | execution | 14 | medium | medium | no |
| EIP-7906 | Transaction Assertions via State Diff Opcode | PFI | execution | 28 | high | medium | yes |
| EIP-7923 | Linear, Page-Based Memory Costing | PFI | execution | 23 | high | medium | yes |
| EIP-7979 | Call and Return Opcodes for the EVM | PFI | execution | 16 | medium | medium | yes |
| EIP-8025 | Optional Execution Proofs | PFI | execution, consensus | 21 | medium | medium | yes |
| EIP-8077 | eth/XX - announce transactions with nonce | PFI | execution | 15 | medium | medium | yes |
| EIP-8094 | eth/vhash - Blob-Aware Mempool | PFI | execution | 20 | medium | medium | yes |
| EIP-8115 | Batch priority fees at end of block | PFI | execution | 16 | medium | medium | yes |
| EIP-8116 | Replace cumulative receipt fields | PFI | execution | 10 | low | medium | yes |
| EIP-8131 | Unified Transaction Content Floor | PFI | execution | 18 | medium | medium | yes |
| EIP-8141 | Frame Transaction | CFI | execution | 60 | high | medium | yes |
| EIP-8146 | Block Access List Sidecars | PFI | execution, consensus | 20 | medium | medium | yes |
| EIP-8148 | Custom sweep threshold for validators | PFI | execution, consensus | 27 | high | medium | yes |
| EIP-8151 | Account Code Restricted ecRecover | PFI | execution | 22 | medium | medium | yes |
| EIP-8182 | Private ETH and ERC-20 Transfers | PFI | execution | 20 | medium | medium | yes |
| EIP-8188 | Last-Written Block for Accounts and Slots | PFI | execution | 26 | high | medium | yes |
| EIP-8200 | EVMification | PFI | execution | 28 | high | medium | yes |
| EIP-8205 | Withdrawal credentials preregistration | PFI | execution, consensus | 24 | high | medium | yes |
| EIP-8237 | Independent CL/EL Sync | PFI | execution, consensus | 29 | high | medium | yes |
| EIP-8250 | Keyed Nonces for Frame Transactions | PFI | execution | 42 | high | medium | yes |
| EIP-8253 | Bump nonce of zero-nonce storage accounts | PFI | execution | 20 | medium | medium | yes |
| EIP-8272 | Recent Roots for Frame Transactions | PFI | execution | 39 | high | medium | yes |
| EIP-8279 | Block Access List Byte Floor | PFI | execution | 29 | high | medium | yes |
| EIP-8298 | SETCODEFROM Code Reuse Instruction | PFI | execution | 22 | medium | medium | yes |
| EIP-8304 | Trustless log and transaction index | PFI | execution | 30 | high | medium | yes |
| EIP-8368 | CPSB Recalibration for New Gas Limit | PFI | execution | 12 | medium | medium | yes |
| EIP-8372 | Normalized state gas limit | PFI | execution | 19 | medium | medium | yes |

## Not applicable to the EL rubric

| EIP | Proposal | Snapshot status | Basis | Rationale |
|---:|---|---|---|---|
| EIP-7716 | Anti-correlation attestation penalties | PFI | consensus only | Changes Beacon State attestation-penalty accounting only and defines no execution-layer behavior. |
| EIP-8015 | Remove `deposit` and `eth1data` fields | PFI | consensus only | Removes deposit and eth1data fields from consensus BeaconBlockBody and BeaconState containers only. |
| EIP-8163 | Reserve `EXTENSION (0xae)` opcode | PFI | explicit owner exclusion | Reserves an EVM opcode value but requires no current L1 execution-client behavior change; the project owner explicitly excluded it from evaluation. |
| EIP-8173 | Foundations of EVM Control Flow | PFI | explicit owner exclusion | Defines an informational execution-layer control-flow model but no protocol or client behavior change; the project owner explicitly excluded it from evaluation. |
| EIP-8243 | Batching Attestations at Source | PFI | consensus only | Changes consensus attestation containers, production, validation, aggregation, and gossip only. |
| EIP-8333 | Align Checkpoint with Epoch Boundary Block | PFI | consensus only | Explicitly makes no execution-layer change and modifies consensus checkpoint selection and fork choice. |
| EIP-8363 | Tapered Issuance Burn | PFI | consensus only | Changes consensus validator issuance, reward, and burn accounting and explicitly requires no execution-layer changes. |

## Caveats

- The original PFI-only result remains 776 across 37 scored EIPs and is not rewritten by this combined view.
- EIP-7805 was SFI and EIP-8141 was CFI, rather than PFI, at the frozen 2026-08-26 snapshot.
- Scores cover execution-layer and execution-client networking surfaces only; EIP-7805 consensus-layer work is not scored.
- Proposal splitting and cross-EIP interactions can overlap complexity, so score sums are not additive implementation-effort estimates.
- No post-snapshot proposal text, implementation evidence, outcomes, or later fork decisions were available to assessors.
