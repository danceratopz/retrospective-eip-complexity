# Task 03: Render fork development timelines

## Objective

Render reproducible, auditable timelines that help a human inspect when development of each fork EIP appears to have begun.

Each fork produces three figure families:

1. a fork overview;
2. execution-layer EIP histories; and
3. consensus-layer EIP histories.

The figures visualize evidence. They do not select or freeze assessment dates and do not assign complexity scores.

## Inputs

Task 01 is the authoritative source for:

- fork membership and layer classification;
- EIP creation dates;
- classified EIP-file revision events; and
- fork-specific inclusion-state events.

Task 03 fork inputs add only information not owned by Task 01:

- the shared calendar window;
- fork milestones and network activations; and
- devnet launch dates and per-EIP participation.

Every supplemental observation references an entry in the fork's Task 03 source registry. Git sources must use immutable commit permalinks. A mutable source may be retained as the canonical discovery URL only when the normalized observation is also reproducible from a pinned Git source.

## Devnet relevance

A devnet appears in an EIP panel only when its `participation` list includes that EIP. A devnet appears in a layer's milestone strip when it contains at least one EIP affecting that layer.

Participation evidence records:

- `explicit_eip_list` when the source names the EIP;
- `explicit_protocol_config` when a pinned network configuration activates an EIP-specific transition;
- `fork_spec_activation` when a layer fork is active but the configuration does not expose a distinct EIP toggle; or
- `series_scope` when the devnet's narrowly defined series and referenced specifications identify the feature.

Confidence and notes remain visible. Planned and cancelled devnets must not be rendered as actual launches.

## Plot semantics

- The x-axis is a shared calendar domain configured once per fork.
- EIP histories use independent y-scales because revision counts vary substantially.
- The primary line counts substantive post-creation EIP-file revisions.
- A faint comparison line counts all post-creation EIP-file revisions.
- The creation commit is a marker, not a revision count.
- Commit points preserve substantive, non-substantive, and uncertain classifications with source links.
- CFI, SFI, removal, and inclusion markers are read from Task 01 without reinterpretation.
- Cross-layer EIPs appear in both layer figures. Their revisions contribute to both layer totals in the overview; the overview labels this overlap explicitly.
- Events before the configured calendar window contribute to the left-edge cumulative baseline.

## Outputs

For each fork:

```text
outputs/<fork>/
├── fork-overview.{html,svg,pdf,vl.json}
├── el-eip-histories.{html,svg,pdf,vl.json}
├── cl-eip-histories.{html,svg,pdf,vl.json}
├── plot-data.json
└── plot-manifest.yaml
```

The HTML files bundle the Vega runtime and work offline. SVG and PDF are publication artifacts; PDF is converted from the deterministic SVG and remains vector-based. Vega-Lite JSON is the canonical visual specification. `plot-data.json` is a derived, inspectable record of the exact observations passed to the charts; Task 01 and the Task 03 inputs remain authoritative.

The manifest records hashes of the renderer, configuration, lockfile, source data, derived plot data, and every generated artifact. It intentionally omits a generation timestamp so identical inputs produce identical research artifacts.

## Reproduction

From this task directory:

```bash
uv sync --locked
uv run --locked python scripts/render.py --fork amsterdam --fork osaka
```

Use `--validate-only` to validate all configured source references and input relationships without writing outputs.

## Acceptance criteria

- The dependency graph is locked in `uv.lock`.
- The same renderer handles every configured fork without fork-specific Python branches.
- Every fork produces all three figure families.
- EL and CL figures contain exactly the EIPs classified for that layer by Task 01.
- Devnet markers appear only for EIPs with recorded participation evidence.
- Planned and cancelled devnets are visually distinct from actual launches.
- Every commit, inclusion event, devnet, and milestone tooltip includes its individual source URL.
- Every HTML artifact is usable without network access.
- All manifests and derived plot data validate on a second clean render.
