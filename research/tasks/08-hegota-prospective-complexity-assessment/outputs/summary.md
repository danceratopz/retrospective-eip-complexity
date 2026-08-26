# Hegotá PFI prospective execution-layer complexity

Snapshot: `hegota-pfi-2026-08-26-ac450a4` at `ac450a4ab2f37387385ee9c54b62f518d97e6cc9` (information cutoff `2026-08-25T11:56:58Z`).

**EL-rubric total: 776 across 37 scored PFI EIPs**. Of 44 PFI entries, 5 are consensus-only and 2 were explicitly excluded; none received a numeric score or tier.

## Scored execution-layer surfaces

| EIP | Proposal | Layers | Score | Tier | Confidence | Under-specified |
|---:|---|---|---:|---|---|---|
| EIP-2488 | Deprecate the CALLCODE opcode | execution | 10 | low | medium | yes |
| EIP-3298 | Remove storage-clear refund and refund cap | execution | 12 | medium | medium | no |
| EIP-4758 | Deactivate SELFDESTRUCT | execution | 14 | medium | medium | yes |
| EIP-5920 | PAY opcode | execution | 16 | medium | medium | yes |
| EIP-7645 | Alias ORIGIN to SENDER | execution | 11 | low | medium | yes |
| EIP-7666 | EVM-ify the identity precompile | execution | 15 | medium | medium | no |
| EIP-7668 | Remove bloom filters | execution | 10 | low | medium | yes |
| EIP-7709 | Read BLOCKHASH from Storage and Update Cost | execution | 20 | medium | medium | yes |
| EIP-7807 | SSZ execution blocks | execution, consensus | 34 | high | medium | yes |
| EIP-7819 | SETDELEGATE instruction | execution | 21 | medium | medium | yes |
| EIP-7851 | Code-Controlled EOA Delegation | execution | 23 | high | medium | yes |
| EIP-7862 | Delayed State Root | execution | 14 | medium | medium | no |
| EIP-7906 | Transaction Assertions via State Diff Opcode | execution | 28 | high | medium | yes |
| EIP-7923 | Linear, Page-Based Memory Costing | execution | 23 | high | medium | yes |
| EIP-7979 | Call and Return Opcodes for the EVM | execution | 16 | medium | medium | yes |
| EIP-8025 | Optional Execution Proofs | execution, consensus | 21 | medium | medium | yes |
| EIP-8077 | eth/XX - announce transactions with nonce | execution | 15 | medium | medium | yes |
| EIP-8094 | eth/vhash - Blob-Aware Mempool | execution | 20 | medium | medium | yes |
| EIP-8115 | Batch priority fees at end of block | execution | 16 | medium | medium | yes |
| EIP-8116 | Replace cumulative receipt fields | execution | 10 | low | medium | yes |
| EIP-8131 | Unified Transaction Content Floor | execution | 18 | medium | medium | yes |
| EIP-8146 | Block Access List Sidecars | execution, consensus | 20 | medium | medium | yes |
| EIP-8148 | Custom sweep threshold for validators | execution, consensus | 27 | high | medium | yes |
| EIP-8151 | Account Code Restricted ecRecover | execution | 22 | medium | medium | yes |
| EIP-8182 | Private ETH and ERC-20 Transfers | execution | 20 | medium | medium | yes |
| EIP-8188 | Last-Written Block for Accounts and Slots | execution | 26 | high | medium | yes |
| EIP-8200 | EVMification | execution | 28 | high | medium | yes |
| EIP-8205 | Withdrawal credentials preregistration | execution, consensus | 24 | high | medium | yes |
| EIP-8237 | Independent CL/EL Sync | execution, consensus | 29 | high | medium | yes |
| EIP-8250 | Keyed Nonces for Frame Transactions | execution | 42 | high | medium | yes |
| EIP-8253 | Bump nonce of zero-nonce storage accounts | execution | 20 | medium | medium | yes |
| EIP-8272 | Recent Roots for Frame Transactions | execution | 39 | high | medium | yes |
| EIP-8279 | Block Access List Byte Floor | execution | 29 | high | medium | yes |
| EIP-8298 | SETCODEFROM Code Reuse Instruction | execution | 22 | medium | medium | yes |
| EIP-8304 | Trustless log and transaction index | execution | 30 | high | medium | yes |
| EIP-8368 | CPSB Recalibration for New Gas Limit | execution | 12 | medium | medium | yes |
| EIP-8372 | Normalized state gas limit | execution | 19 | medium | medium | yes |

## Not applicable to this rubric

| EIP | Proposal | Basis | Rationale |
|---:|---|---|---|
| EIP-7716 | Anti-correlation attestation penalties | consensus only | Changes Beacon State attestation-penalty accounting only and defines no execution-layer behavior. |
| EIP-8015 | Remove `deposit` and `eth1data` fields | consensus only | Removes deposit and eth1data fields from consensus BeaconBlockBody and BeaconState containers only. |
| EIP-8163 | Reserve `EXTENSION (0xae)` opcode | explicit owner exclusion | Reserves an EVM opcode value but requires no current L1 execution-client behavior change; the project owner explicitly excluded it from evaluation. |
| EIP-8173 | Foundations of EVM Control Flow | explicit owner exclusion | Defines an informational execution-layer control-flow model but no protocol or client behavior change; the project owner explicitly excluded it from evaluation. |
| EIP-8243 | Batching Attestations at Source | consensus only | Changes consensus attestation containers, production, validation, aggregation, and gossip only. |
| EIP-8333 | Align Checkpoint with Epoch Boundary Block | consensus only | Explicitly makes no execution-layer change and modifies consensus checkpoint selection and fork choice. |
| EIP-8363 | Tapered Issuance Burn | consensus only | Changes consensus validator issuance, reward, and burn accounting and explicitly requires no execution-layer changes. |

## Caveats

- Scores cover execution-layer and execution-client-networking surfaces only; cross-layer consensus work is not scored.
- EIP-8163 and EIP-8173 were explicitly excluded by the project owner because they introduce no current L1 protocol or client behavior change.
- Proposal splitting and cross-EIP interactions can overlap complexity, so the score sum is not an additive estimate of implementation effort.
- The PFI snapshot may change after the frozen information cutoff; later scope churn is outside this study.
- No consensus-layer rubric was applied, so this is not a total-complexity estimate for all Hegota protocol work.
