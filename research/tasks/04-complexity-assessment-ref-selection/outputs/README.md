# Task 04 outputs

Fork-specific EIP ref proposals live under `fork-eips/<fork-id>/`. Human-review timelines generated from those proposals live under `review/<fork-id>/`.

The review timeline reuses the locked Task 03 renderer. Each EIP panel has fixed event lanes, from top to bottom: the selected historical revision as a large magenta `REF` flag, followed by labelled `PFI`, `CFI`, and `SFI` flags, then relevant devnet/testnet markers at the bottom. The selected ref retains a solid magenta rule, and the proposal anchor is an amber dashed rule. Review status remains available in each assessment marker's tooltip.

A CFI event inherited from a Rollup Improvement Proposal precursor is labelled `CFI (RIP)`; its tooltip retains the precursor's complete identifier and provenance.

Run from the repository root:

```bash
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04-complexity-assessment-ref-selection/scripts/render_review.py --validate-only --fork osaka
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04-complexity-assessment-ref-selection/scripts/render_review.py --fork osaka
```

Do not hand-edit `plot-data.json`, Vega-Lite JSON, manifests, HTML, SVG, or PDF.

One proposed complexity-assessment EIP ref is written per fork–EIP relationship under `fork-eips/<fork-id>/`. Records remain proposals until their `review.status` is changed to `approved` by a separate review step.

Do not hand-edit agent-owned outputs while a fork run is active.
