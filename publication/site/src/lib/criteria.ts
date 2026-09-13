/**
 * Presentation registry for the 29 rubric criteria: group, colour, abbreviation, and display order.
 *
 * Criterion identifiers, labels, definitions, and rubric membership come from the publication payload
 * (`data.criteria`). This module only adds the visual identity that has to be identical everywhere a
 * criterion appears: stacked bars, legends, comparison matrices, and criterion tables.
 *
 * Colour follows the data-viz method: seven criterion groups take the first seven slots of the
 * documented categorical palette in fixed order (blue, orange, aqua, yellow, magenta, green, violet);
 * members of a group are OKLCH lightness steps of the group hue. Group hues were validated as an
 * adjacent categorical palette and each ramp as an ordinal ramp on the white surface. Light steps sit
 * below 3:1 contrast, so identity never relies on colour alone: every segment also carries an
 * abbreviation label, an accessible name, and a legend or table entry.
 */

export interface CriterionGroup {
  id: string;
  label: string;
  description: string;
  hue: string;
}

export const CRITERION_GROUPS: CriterionGroup[] = [
  { id: 'evm_surface', label: 'EVM surface', description: 'Opcodes, precompiles, and system contracts that are added or modified.', hue: 'blue' },
  { id: 'gas', label: 'Gas and accounting', description: 'Execution, blob, and state gas rules, refunds, and where charges happen inside opcodes.', hue: 'orange' },
  { id: 'structure', label: 'Blocks, transactions, and encoding', description: 'Transaction types and validity, block and header fields, encodings, syncing, and activation-time changes.', hue: 'aqua' },
  { id: 'interfaces', label: 'Client interfaces', description: 'Engine API and transition-tool interface changes.', hue: 'yellow' },
  { id: 'testing', label: 'Testing impact', description: 'Rework, new invariants, and new primitives required in the test framework.', hue: 'magenta' },
  { id: 'risk', label: 'Risk and validation', description: 'Security, performance, boundary conditions, and cryptography that need validation.', hue: 'green' },
  { id: 'coordination', label: 'Coordination', description: 'Cross-EIP interactions and behavior that clients must agree on before tests exist.', hue: 'violet' },
];

interface Presentation {
  group: string;
  abbreviation: string;
  color: string;
}

/** Display order is group order, then the order below within a group. */
export const CRITERION_PRESENTATION: Record<string, Presentation> = {
  added_opcodes: { group: 'evm_surface', abbreviation: 'OP+', color: '#7bb4fe' },
  modified_opcodes: { group: 'evm_surface', abbreviation: 'OP~', color: '#549ffe' },
  added_precompiles: { group: 'evm_surface', abbreviation: 'PC+', color: '#3e8beb' },
  modified_precompiles: { group: 'evm_surface', abbreviation: 'PC~', color: '#2978d6' },
  added_system_contracts: { group: 'evm_surface', abbreviation: 'SC+', color: '#1064c1' },
  modified_system_contracts: { group: 'evm_surface', abbreviation: 'SC~', color: '#0053a6' },
  evm_gas_rule_changes: { group: 'gas', abbreviation: 'GAS', color: '#fe8e65' },
  state_access_ordering_within_opcode_execution: { group: 'gas', abbreviation: 'ORD', color: '#ef6c38' },
  blob_gas_accounting_changes: { group: 'gas', abbreviation: 'BLOB', color: '#d4531a' },
  state_gas_accounting_changes: { group: 'gas', abbreviation: 'SGAS', color: '#b43f01' },
  new_evm_gas_refund: { group: 'gas', abbreviation: 'RFND', color: '#913101' },
  new_transaction_types: { group: 'structure', abbreviation: 'TX+', color: '#48cc95' },
  new_or_modified_transaction_validity_mechanisms: { group: 'structure', abbreviation: 'TXV', color: '#2cb883' },
  new_block_header_fields: { group: 'structure', abbreviation: 'HDR', color: '#02a471' },
  encoding_changes_rlp_ssz: { group: 'structure', abbreviation: 'ENC', color: '#038f61' },
  block_syncing_changes: { group: 'structure', abbreviation: 'SYNC', color: '#047a53' },
  new_fork_activation_mechanism: { group: 'structure', abbreviation: 'ACT', color: '#006644' },
  engine_api_changes: { group: 'interfaces', abbreviation: 'ENG', color: '#eba008' },
  engine_api_encoding_changes: { group: 'interfaces', abbreviation: 'ENGE', color: '#ad7502' },
  transition_tool_interface_changes: { group: 'interfaces', abbreviation: 'T8N', color: '#734c00' },
  patterns_affecting_pre_existing_tests: { group: 'testing', abbreviation: 'TEST', color: '#f789b2' },
  new_invariant_on_pre_existing_tests: { group: 'testing', abbreviation: 'INV', color: '#c25982' },
  new_test_framework_primitives: { group: 'testing', abbreviation: 'PRIM', color: '#8e2956' },
  security_risks: { group: 'risk', abbreviation: 'SEC', color: '#63cd5d' },
  performance_risks: { group: 'risk', abbreviation: 'PERF', color: '#40ab3b' },
  edge_boundary_conditions: { group: 'risk', abbreviation: 'EDGE', color: '#148b11' },
  cryptography: { group: 'risk', abbreviation: 'CRYP', color: '#006900' },
  cross_eip_interactions: { group: 'coordination', abbreviation: 'XEIP', color: '#a7a6ff' },
  unspecified_behavior_requiring_cross_client_consensus: { group: 'coordination', abbreviation: 'UNSP', color: '#4e3fac' },
};

/** Site-wide stable criterion order: grouped, as listed above. */
export const DISPLAY_ORDER: string[] = Object.keys(CRITERION_PRESENTATION);
export const DISPLAY_INDEX: Map<string, number> = new Map(DISPLAY_ORDER.map((id, index) => [id, index]));

export function presentation(id: string): Presentation {
  const entry = CRITERION_PRESENTATION[id];
  if (!entry) throw new Error(`No presentation registered for criterion ${id}`);
  return entry;
}

export function criterionColor(id: string): string {
  return presentation(id).color;
}

export function criterionAbbreviation(id: string): string {
  return presentation(id).abbreviation;
}

/** Text colour for a label painted inside a criterion fill, chosen by the fill's luminance. */
export function inkOn(id: string): string {
  const hex = criterionColor(id).replace('#', '');
  const [r, g, b] = [0, 2, 4].map((index) => Number.parseInt(hex.slice(index, index + 2), 16) / 255);
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return luminance > 0.36 ? '#17202a' : '#ffffff';
}

export function sortByDisplayOrder<T extends { id: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => (DISPLAY_INDEX.get(a.id) ?? 99) - (DISPLAY_INDEX.get(b.id) ?? 99));
}

/** CSS custom properties consumed by every criterion-coloured element. */
export function criterionCss(): string {
  const lines = Object.entries(CRITERION_PRESENTATION).map(
    ([id, entry]) => `  --criterion-${id}: ${entry.color};\n  --criterion-ink-${id}: ${inkOn(id)};`,
  );
  return `:root {\n${lines.join('\n')}\n}`;
}

/** Fail the build if the payload and the presentation registry disagree. */
export function assertRegistryMatches(ids: string[]): void {
  const missing = ids.filter((id) => !CRITERION_PRESENTATION[id]);
  const extra = DISPLAY_ORDER.filter((id) => !ids.includes(id));
  if (missing.length || extra.length) {
    throw new Error(`Criterion presentation registry mismatch: missing ${missing.join(', ') || 'none'}; extra ${extra.join(', ') || 'none'}`);
  }
  const abbreviations = new Set(DISPLAY_ORDER.map((id) => CRITERION_PRESENTATION[id].abbreviation));
  if (abbreviations.size !== DISPLAY_ORDER.length) throw new Error('Criterion abbreviations must be unique');
}
