# EIP-NNNN: EIP Title

Checklist revision: **3** (28 criteria)

Link: https://eips.ethereum.org/EIPS/eip-NNNN

## Execution Specs

### Specs

TBD

### Testing

#### Assessment basis

Assess additional execution-layer testing work caused by the target EIP. Include execution-client support for cross-layer changes; exclude changes confined to consensus clients. Complexity describes the required testing work, not the importance of the feature or the number of lines in its specification.

Use the stated base fork plus the changes required by the target as the assessment baseline, including prerequisites proposed for the same fork. Required prerequisites are mechanisms the target specification depends on, whether or not listed in `requires`. “New”, “existing” and “modified” refer to this conditional baseline. Attribute inherited mechanisms and their base testing capabilities to their defining EIPs; count changes and additional regression or interaction tests required by the target. This assessment baseline does not imply an activation order or include unrelated proposals. Scores for related EIPs need not sum to the testing cost of implementing their whole bundle.

Base the assessment on supplied evidence. A dependency reference alone does not establish its behavior. The target’s description of a prerequisite is usable evidence, but does not independently verify that prerequisite. Record supporting sources and material evidence gaps in Rationale. Claims about framework capabilities, client agreement or devnet experience require supporting evidence. Missing evidence is neither a score of 0 nor a reason for a high score.

Describe the concrete rule, validation boundary or test family affected. A test family groups cases exercising the same protocol behavior; fixtures differing only in parameters are not separate families. “Existing tests” means tests needed for the conditional baseline, not an assertion that particular test files exist.

#### Criteria

All criteria are scored on a 0–3 scale. Use only the levels listed for each criterion. A score of 4 may be used in exceptional circumstances only when the criterion's level-3 condition applies and supplied evidence establishes additional testing work beyond that condition within this same criterion.

Choose the highest level whose full definition is supported. Do not use 4 for uncertainty, missing evidence, the prerequisite's complexity, or an unrelated risk.

In the abbreviations below, `+` means added and `~` means modified.

##### GAS — EVM Gas rule changes

Changes execution-gas charging, metering, limits or settlement. A mechanism is an accounting rule, not an ordinary contract fee or use of an existing instruction. State and blob gas have separate criteria.
- 0. No execution-gas accounting rule changes.
- 1. Existing accounting rules or parameters change without introducing a new accounting mechanism.
- 2. A new accounting mechanism is added without changing existing accounting rules or the expected gas results of baseline operations.
- 3. A new accounting mechanism also changes existing accounting rules or the expected gas results of baseline operations.

##### SAO — State-access ordering within opcode execution

Changes when an instruction accesses state or charges gas relative to that access, including which accesses enter the block-level access list. Count changed ordering, not the mere presence of state access.

- 0. No instruction's state-access or gas-charge ordering changes, and no new ordering rule is introduced.
- 1. Ordering changes for exactly one existing opcode, without a general rule change.
- 2. Ordering changes for multiple opcodes, or a new state-accessing operation needs an ordering rule, without meeting level 3.
- 3. A common ordering rule changes for an entire opcode class, or the definition of a recordable access changes across operations, requiring baseline access-list expectations to be revised.

*Changed precompile or contract internals do not modify an instruction's ordering unless the instruction's own specified sequence changes. Record relevant combinations such as cold/warm, static/non-static and revert/success; do not assume every combination applies. Record multiplicative growth across applicable combinations under Special Considerations.

##### BLOB — Blob gas accounting changes

Changes blob-gas charging, pricing, limits or settlement. Carrying existing blobs or changing blob-related validity checks alone does not change accounting.

- 0. No blob-gas accounting rule changes.
- 1. Existing accounting rules or parameters change without introducing a new mechanism.
- 2. A new mechanism is added without changing existing accounting rules or baseline gas expectations.
- 3. A new mechanism also changes existing accounting rules or baseline gas expectations.

##### SGAS — State gas accounting changes

Changes protocol accounting for writing state, including state-byte costs, state-gas budgets and spill into execution gas. Using an unchanged state-writing operation does not introduce accounting. State-access charges, including cold/warm access, and block-access-list data-size charges alone belong under EVM Gas rule changes, not state gas accounting.

- 0. No state-gas accounting rule changes.
- 1. Only existing cost parameters or state-byte rates change.
- 2. Charging is added at a new site using an existing mechanism, or budget/reservoir allocation changes, without meeting level 3.
- 3. A new state-gas charging mechanism is introduced, or spill between state and execution gas changes baseline accounting expectations.

##### RFND — New EVM gas refund

Introduces an additional protocol refund mechanism. “Simple” means one local trigger without history-dependent eligibility or interaction with other refund rules; other mechanisms are complex. Repricing or removing an existing refund belongs under EVM Gas rule changes.

- 0. No new refund mechanism is introduced.
- 1. All new refund mechanisms are simple and leave existing refund rules and baseline expectations unchanged.
- 2. A complex mechanism is added without changing baseline refund behavior, or only simple mechanisms are added but change that behavior.
- 3. A complex mechanism is added and changes existing refund rules or baseline refund expectations.

##### PAT — Patterns affecting pre-existing tests

Baseline tests need changed inputs, execution steps or expected results because of the target. Exclude the work of constructing prerequisite test suites, new tests solely for the added feature, and merely appending an assertion.

- 0. No baseline test behavior needs reworking.
- 1. Rework is confined to particular parameter or boundary cases within one behavioral family.
- 2. Rework affects ordinary cases throughout one family, or localized cases in several families, without a common rewrite across families.
- 3. A common change requires reworking ordinary cases across distinct behavioral families; identify the changed rule and affected families.

*Estimate required behavioral coverage from the specification. Do not claim measured test counts without a supplied suite.

##### INV — New invariant on pre-existing tests

Baseline tests must additionally check an output that did not exist before the target, such as a new log, header or receipt field, block commitment or protocol-mandated storage write produced while they run. Changed gas costs, limits or existing expected values are rework under Patterns affecting pre-existing tests, not a new assertion. Attribute an assertion introduced by a prerequisite to that prerequisite.

- 0. Baseline tests need no additional assertion.
- 1. Only a restricted parameter or boundary subset within one family needs the assertion.
- 2. Ordinary cases across one or more families need the assertion, but level 3 is not met.
- 3. Every test in the target fork needs the assertion regardless of its subject, and pre-fork vectors must also be re-derived; both requirements need evidence.

*A universal assertion without pre-fork vector changes is level 2.

##### T8N — Transition-tool interface changes

Changes the execution state-transition tool's inputs, outputs or invocation protocol. Count distinct semantic fields, not repeated schema occurrences. A new mechanism changes the tool's operation or exchange sequence beyond passing ordinary fields.

- 0. No transition-tool interface change is required.
- 1. Exactly one field is added, removed or semantically changed, without a new mechanism.
- 2. Multiple fields change without a new mechanism, or a new mechanism is required with at most one changed field.
- 3. A new mechanism and multiple changed fields are both required.

*Fork-aware behavior counts here only if it requires an interface change. Actual interface reuse needs supplied tool evidence.

##### FWK — New test-framework primitives

Requires additional framework capabilities beyond those needed for the prerequisites. A new test, vector, contract or parameter value alone is not a new primitive. Assess architectural necessity without assuming actual helper availability.

- 0. No additional abstraction is required beyond baseline primitives.
- 1. An existing kind of primitive needs a local extension, without a new abstraction.
- 2. A new expectation, modifier or construction abstraction is required within the target's test suite, without meeting level 3.
- 3. The target requires a shared framework representation or execution facility that also changes how other behavioral families are constructed or checked; hypothetical future reuse is insufficient.

##### CRYP — Cryptography

Introduces or changes cryptographic verification, signing, hashing or proof rules executed by the EL. Reusing an unchanged primitive and protocol validation rule is not another mechanism. An established mechanism needs supplied evidence of applicable specifications and test resources; unfamiliarity is not novelty.

- 0. No cryptographic mechanism or cryptographic validation rule changes.
- 1. Exactly one established mechanism is added or changed, with applicable test resources evidenced.
- 2. Multiple mechanisms are added or changed and all are established with applicable resources, or exactly one mechanism is added or changed and requires validation beyond established resources.
- 3. Multiple mechanisms are added or changed and at least one requires cryptographic validation beyond established resources.

*Changed message bytes using unchanged hashing/signing rules alone belong to encoding or validity testing. Missing information about resources is an evidence gap, not proof of novelty.

##### EDGE — Edge/boundary conditions

Count independent changed rules with boundary-sensitive outcomes, not individual boundary values. An elevated matrix means interacting dimensions whose combinations change the result and cannot be tested independently.

- 0. No new or changed boundary-sensitive rule is identified.
- 1. Exactly one boundary-sensitive mechanism changes or is introduced.
- 2. Multiple boundary-sensitive mechanisms change or are introduced, with no elevated matrix.
- 3. Multiple boundary-sensitive mechanisms change or are introduced and at least one has an elevated matrix; identify its interacting dimensions.

*A single boundary-sensitive mechanism remains level 1 even with an elevated matrix; it does not meet the level-3 prerequisite for exceptional 4. Record unusually broad combinations under Special Considerations.

##### SYNC — Block syncing changes

Changes execution-block RLP decoding or structural validation that must be tested through block import/sync. Other synchronization work is outside this criterion. Simple checks validate one field locally; complex checks depend on other fields, blocks or state.

- 0. No execution-block RLP decoding or structural validation rule changes.
- 1. Exactly one simple validation rule is added or changed.
- 2. Multiple simple rules change, or exactly one complex rule changes.
- 3. Multiple rules change and at least one is complex.

*Exclude mempool gossip, CL-only sync and optional indexing. Ordinary execution-rule changes alone do not satisfy this criterion.

##### ENG — Engine API changes

Changes the EL/CL Engine API contract. Count distinct semantic fields once even when repeated across methods. A new versioned method counts as an endpoint; changing a field's type or meaning counts as a field change. Exclude public JSON-RPC, transition-tool and application APIs.

- 0. No Engine API field or endpoint changes.
- 1. Exactly one field changes, without adding or changing endpoint behavior beyond that field.
- 2. Multiple fields change without an endpoint-level change, or endpoint behavior changes with at most one field change.
- 3. Endpoint behavior and multiple fields both change.

*Endpoint-level changes include adding/removing a method or changing its exchange or response-status rules, beyond ordinary field changes.

##### +SC — Added system contracts

Introduces protocol-designated EVM contracts, counted by distinct protocol-designated deployments, including addresses still TBD. Exclude native precompiles and ordinary application contracts. “Stateful” means persistent storage; a “system action” is a protocol effect beyond the ordinary call result, such as an execution request.

- 0. No system contract is introduced beyond the prerequisites.
- 1. Exactly one stateless contract is introduced, without a new system action.
- 2. Multiple stateless contracts without system actions are introduced, or exactly one contract is introduced that is stateful or triggers a system action.
- 3. Multiple contracts are introduced and at least one is stateful or triggers a system action.

##### ~SC — Modified system contracts

Changes an existing protocol-designated contract's rules, required code or state layout, or the protocol behavior around it. Ordinary writes under unchanged contract rules are not modifications. Exclude native precompiles and application contracts.

- 0. No existing system contract's rules or surrounding protocol behavior change.
- 1. Contract rules stay unchanged, but one local input or output convention changes indirectly.
- 2. Contract rules stay unchanged, but indirect changes alter sequencing, state assumptions or interactions beyond one local convention.
- 3. An existing contract's specified behavior, required code, storage layout or protocol-mandated state changes directly.

*A direct change does not automatically imply an activation migration. Assess activation-specific work separately.

*Deploying a newly introduced system contract is not modifying an existing one, including when code is installed at an already-existing account with empty code and storage. Assess that deployment under Added system contracts and any activation-specific work under New fork activation mechanism. Changes to a system contract already present in the prerequisite baseline still count here.

##### +OP — Added opcodes

Introduces previously undefined EVM instructions. Simple means no immediate data, fixed stack effects and constant gas; an instruction lacking any of these properties is complex. A prerequisite's instruction already exists in the baseline.

- 0. No new instruction is introduced.
- 1. Exactly one simple instruction is introduced.
- 2. Multiple simple instructions are introduced, or exactly one complex instruction.
- 3. Multiple instructions are introduced and at least one is complex.

*Contract bytecode, transaction frames and new introspection selector values are not new opcodes. Replacing an existing instruction's semantics belongs under Modified opcodes. Cryptography alone does not determine this criterion's complexity.

##### ~OP — Modified opcodes

Changes an existing EVM instruction's semantics or availability, including an instruction defined by a same-fork prerequisite. Semantics include stack, memory/state effects, emitted logs, control flow, return values and exceptional halts.

- 0. No instruction's specified semantics or availability changes. Gas-only changes, access ordering alone, and changed callee or precompile behavior through an unchanged instruction do not count.
- 3. At least one instruction's specified semantics or availability changes beyond gas-only or access-ordering changes, or an existing instruction is deprecated.

*New selector behavior within an existing introspection instruction is a modification. Merely calling new contract code is not.

##### +PC — Added precompiles

Introduces native execution functions at protocol-defined precompile addresses. Count distinct addresses. Simple means fixed supported input length and constant gas; variable supported input length or dynamic gas makes a precompile complex.

- 0. No new precompile is introduced.
- 1. Exactly one simple precompile is introduced.
- 2. Multiple simple precompiles are introduced, or exactly one complex precompile.
- 3. Multiple precompiles are introduced and at least one is complex.

*Exclude EVM system contracts. Cryptography alone does not determine this criterion's complexity.

##### ~PC — Modified precompiles

Changes existing precompile semantics or gas schedules. For this criterion, complex means variable supported input length or dynamic gas before or after the change. Behavior means outputs, accepted inputs or failure rules beyond gas alone.

- 0. No existing precompile's semantics or gas schedule changes.
- 1. Exactly one precompile has a gas-only change, and none has a behavior change.
- 2. Multiple precompiles have gas-only changes and none has a behavior change, or exactly one simple precompile has a behavior change and no other precompile has a behavior change.
- 3. Multiple precompiles have behavior changes, or at least one complex precompile has a behavior change.

##### ENC — Encoding changes (RLP/SSZ)

Changes a serialized schema or codec for EL transactions, blocks/headers, receipts, execution requests, protocol account/state-trie records, Engine API, execution-client peer messages or protocol-specified EL proof interfaces. RLP/SSZ are examples, not an exhaustive codec list.

- 0. No schema or codec changes in those objects/interfaces. New values within unchanged schemas, ordinary contract calldata/storage layouts and CL-only containers do not count.
- 3. At least one listed object/interface gains or changes a serialized field, format or codec, including a new request payload schema within an existing request-type scheme.

*Name the object and schema change. Retaining RLP, SSZ or JSON does not exclude a schema change. This can overlap a transaction, header or API criterion because it measures separate serialization work.

##### TX — New transaction types

Introduces a distinct EL transaction envelope accepted in an execution block's transaction list. In the typed scheme, this means an EIP-2718 type with its own payload definition and allocated or proposed discriminator; a TBD type byte still counts.

- 0. No new EL transaction envelope is introduced. Execution-request types, contract calls/calldata, CL operations, system calls and inner transaction frames do not count; modifying an existing type does not itself introduce one.
- 3. At least one distinct EL transaction envelope is introduced beyond the prerequisites, with its own payload definition and transaction-type discriminator, allocated or proposed.

##### TXV — New or modified transaction validity mechanisms

Changes consensus rules determining transaction eligibility in an execution block, including intrinsic gas and rules for new types. Exclude public-mempool policy alone, application-level reverts, precompile outputs and CL request acceptance.

- 0. No consensus transaction-validity or intrinsic-gas rule changes.
- 1. Only a local parameter, bound or existing condition changes, without introducing a new validation dependency or sequence.
- 2. New or changed validation rules require dedicated cases or local test extensions, while baseline validation sequencing and test construction remain usable.
- 3. Validation changes require restructuring shared test construction, validation sequencing or coordinated transaction/state scenarios beyond local cases; identify the required restructuring.

*Inherited validation is not introduced again. A new condition alone does not establish framework redesign. A consensus rule change can require extensive work even when its textual delta is short.

##### HDR — New block / header fields

Adds an EL block-level or execution-header schema member that clients must read, produce or validate. Count a field where its owning schema is defined.

- 0. No EL block-level or execution-header member is added. Changed field values/meanings, list entries, transaction/request payload fields, CL-only fields and API-only fields do not count.
- 3. At least one EL block-level or execution-header member is added; identify its containing schema.

*An additional request type under an existing requests commitment is not another header field. An Engine API field counts here only when its corresponding EL block/header member is also added.

##### FORK — New fork activation mechanism

Requires an activation-specific EL transition: one-time migration/reset/conversion of persistent state, or protocol-mandated installation/replacement of account code or storage. A conditional prerequisite baseline does not imply earlier activation.

- 0. No activation-specific EL transition is required. Rule/constant selection, new internal bookkeeping, ordinary deployment transactions and starting recurring block processing alone do not count.
- 3. At least one activation-specific EL state transition is required; identify the operation that differs from ordinary post-fork processing.

*A one-time conversion of pre-fork state can count when embedded in a recurring system call. New-account installation mandated at activation counts. CL-only transitions do not.

##### PERF — Performance risks

Requires performance validation of additional or changed EL workloads. Name the resource and changed bound or interaction. The prerequisite's cost or generic concern about denial of service is insufficient.

- 0. No additional performance-validation requirement is established by the change.
- 1. Component benchmarks cover the changed workload without changing baseline end-to-end performance assumptions.
- 2. Targeted integrated benchmarks are needed for a bounded interaction, even if part of the mechanism can also be benchmarked alone.
- 3. New resource coupling or adversarial workload combinations require integrated stress testing across distinct execution/client subsystems; identify the affected assumptions.

*Changes to gas costs or resource limits can require renewed benchmarking of existing workloads even when the underlying mechanisms are unchanged. Score the validation required by the changed workload capacity or resource bound; exclude the prerequisite's original benchmarking effort.

##### SEC — Security risks

Requires validation of new or changed security invariants or failure modes. Name what the target changes and the affected boundary. Every implementation can contain bugs; that fact alone is not a scoring condition.

- 0. No additional security-sensitive rule or validation boundary is introduced or changed.
- 1. New or changed security conditions can be checked locally without changing assumptions used by other components.
- 2. A bounded interaction changes another component's security assumptions and needs targeted integration review or fuzzing.
- 3. A shared authorization, trust or validation invariant changes across multiple components, requiring coordinated adversarial scenarios beyond a bounded interaction.

*Inherited security properties do not score again. Severity alone does not determine testing breadth; a critical but local check may remain level 1 or 2.

##### UNSP — Unspecified behavior requiring cross-client consensus

The supplied normative specification leaves a constructible, observable protocol outcome unresolved. Distinguish actual omissions or contradictions from dependency text or implementation history missing from the assessment packet.

- 0. No unresolved protocol outcome is identified in the supplied rules; missing external evidence alone is not an omission in the specification.
- 1. A localized detail is omitted but the supplied surrounding rules support one intended outcome without competing normative interpretations.
- 2. Localized competing outcomes or contradictory rules require specification/client agreement before expected results can be fixed.
- 3. Previously unspecified and previously unobservable behavior becomes consensus-visible, requiring agreement on a shared rule and re-baselining across behavioral families.

*Use the supplied specification version. Do not infer devnet maturity, implementation agreement or discussion outcomes. If an absent dependency might define the behavior, mark the evidence gap rather than asserting it is unspecified.

##### XEIP — Cross-EIP interactions

Additional coordinated cases are needed because the target's new or changed behavior interacts with behavior defined by another EIP, including behavior whose defining rules are unchanged. Identify the interaction, not merely the citation or dependency. Inherited prerequisite tests, unchanged ancestor mechanisms and optional application designs do not automatically count.

- 0. No additional interaction tests with another EIP are required; dependencies may be present but unaffected in this sense.
- 1. Interactions need only local compatibility checks; the target's behavior can otherwise be tested independently.
- 2. At least one interaction needs coordinated cross-EIP cases, without the coupled multi-EIP test restructuring in level 3.
- 3. The target's changes couple behavior from multiple EIPs, requiring coordinated scenarios across those interactions or restructuring shared vectors; the other EIPs' own rules need not change. A list of dependencies alone is insufficient.
- **+1 for every 3 additional interacting EIPs beyond the first 3**, each requiring target-specific coordinated cases. Count each EIP once and identify those cases. Exclude mere citations and tests of the other EIP's own behavior.

*Add the bonus to the base score at any level; it depends only on the number of qualifying EIPs. Count only EIPs needing their own target-specific coordinated cases; local compatibility checks alone do not qualify for the bonus. Interacting EIPs may be from past forks or the assessed same-fork scenario and need not be prerequisites; identify that scenario. Exceptional 4 is not a substitute for the bonus. Missing dependency semantics may leave an interaction unresolved rather than absent.


### Checklist

| Abbrev. | Criterion | Score (0–3) | Rationale |
|---|---|---:|---|
| `GAS` | **EVM Gas rule changes** |   |   |
| `SAO` | **State-access ordering within opcode execution** |   |   |
| `BLOB` | **Blob gas accounting changes** |   |   |
| `SGAS` | **State gas accounting changes** |   |   |
| `RFND` | **New EVM gas refund** |   |   |
| `PAT` | **Patterns affecting pre-existing tests** |   |   |
| `INV` | **New invariant on pre-existing tests** |   |   |
| `T8N` | **Transition-tool interface changes** |   |   |
| `FWK` | **New test-framework primitives** |   |   |
| `CRYP` | **Cryptography** |   |   |
| `EDGE` | **Edge/boundary conditions** |   |   |
| `SYNC` | **Block syncing changes** |   |   |
| `ENG` | **Engine API changes** |   |   |
| `+SC` | **Added system contracts** |   |   |
| `~SC` | **Modified system contracts** |   |   |
| `+OP` | **Added opcodes** |   |   |
| `~OP` | **Modified opcodes** |   |   |
| `+PC` | **Added precompiles** |   |   |
| `~PC` | **Modified precompiles** |   |   |
| `ENC` | **Encoding changes (RLP/SSZ)** |   |   |
| `TX` | **New transaction types** |   |   |
| `TXV` | **New or modified transaction validity mechanisms** |   |   |
| `HDR` | **New block / header fields** |   |   |
| `FORK` | **New fork activation mechanism** |   |   |
| `PERF` | **Performance risks** |   |   |
| `SEC` | **Security risks** |   |   |
| `UNSP` | **Unspecified behavior requiring cross-client consensus** |   |   |
| `XEIP` | **Cross-EIP interactions** (uncapped) |   |   |

**Total: X**

#### Special Considerations

> Evaluator must write here special considerations that make the EIP particularly complex to test due to reasons not directly included in this checklist.

#### Notes

> Evaluator notes that do not affect the score but are valid points that must be taken into consideration when the tests are being written.

Record the assessed EIP revision, template revision, base fork, required prerequisites, supporting sources and material assumptions. For automated assessments, also record the model and evaluator-instruction versions. Assessments using different evidence or baselines are not directly interchangeable.

#### Final Assessment

| Category | Description | Value |
|-----------|--------------|:----:|
| **Total Score** | Sum of all criterion scores (0–84 nominal; **Cross-EIP interactions** is uncapped, so there is no hard maximum) | **`XX`** |
| **Complexity Tier** | Computed from total score | 🟢 / 🟡 / 🔴 |

##### Tier Interpretation

| Tier | Range | Meaning |
|------|--------|----------|
| 🟢 **Low Complexity** | **<12** | Minor feature or localized change. Existing tests are largely unaffected. Does not require intensive cross-EIP testing. |
| 🟡 **Medium Complexity** | **>=12<23** | Moderate change affecting multiple components. Requires moderate cross-EIP testing. |
| 🔴 **High Complexity** | **>=23** | Broad or deep impact on protocol behavior; high regression risk; and/or requiring intensive cross-EIP testing. |

## Consensus Specs

### Specs

### Testing

### Notes
