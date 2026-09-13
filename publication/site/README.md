# Study site

Astro static site for the EIP complexity study. It renders the sanitized payload produced by
`publication/scripts/build_records.py`; it never reads research records directly.

```bash
npm ci
npm run check    # regenerate data deterministically and type-check
npm run build    # regenerate data and build dist/
npm test         # adapter unit tests and the built-site validator
npm run preview -- --host 127.0.0.1 --port 4321
```

## Architecture

The site is organised around one domain model and one set of shared components.

```text
publication.json (schema 2.0.0)
  criteria[]      29 rubric criteria with labels, definitions, anchors, rubric membership
  rubrics{1,2}    criterion order, nominal maximum, tier thresholds per checklist revision
  eips[]          EIP -> occurrences[] (one per fork) -> llm/human summaries, assessment_ids, comparison_ids
  assessments{}   one object per (fork, EIP, evaluator, rubric revision): status, scored, score, tier,
                  criteria[] with rationale/evidence/uncertainty, under_specification, provenance
  comparisons{}   same-rubric Human vs LLM pairs with per-criterion deltas and agreement classes
  forks[]         totals, cutoff split, criterion composition blocks, human coverage
compare-index.json  compact per-assessment criterion scores for the client-side comparison
```

| Layer | Files | Responsibility |
| --- | --- | --- |
| Data loading | `src/lib/data.js` | Read the generated payload at build time; base-path helper |
| Domain | `src/lib/domain.ts` | Types and pure accessors: occurrences, assessments, view modes, criterion partitioning, top drivers, compositions, score bands |
| Terminology | `src/lib/labels.ts` | Every reader-facing term: sources, statuses, tiers, confidence, under-specification wording |
| Criterion identity | `src/lib/criteria.ts` | Group, colour, abbreviation, and display order per criterion; emits the CSS custom properties |
| Routing and view state | `src/lib/routes.ts` | Base-aware URL builders and query codecs for the EIP page and the comparison |
| Stacked bars | `src/lib/stacked-bar.ts`, `components/StackedBar.astro` | One HTML renderer used server-side and client-side |
| Assessment views | `AssessmentView`, `AssessmentSummary`, `TopDrivers`, `UncertaintySection`, `CriterionTable`, `ProvenanceDetails` | Explain one assessment; identical for Human and LLM evaluators |
| Comparison | `AssessmentCompare.astro` (Human vs LLM on one EIP), `lib/compare-view.ts` + `pages/eips/compare.astro` (up to four EIPs) | Difference-oriented comparison |
| Status | `StatusBadge`, `EvaluatorBadge`, `TierBadge` | Shared badges so missing, incomplete, and not-applicable states never look like zero |
| Pages | `pages/eips/[eip].astro` → `EipDetail`; `pages/forks/[fork].astro` and `pages/prospective/hegota.astro` → `ForkPage`; `pages/eips/index.astro` → `OccurrenceTable`; `pages/results/…` → `ForkComposition` | Thin page files over shared components |

### URL state

| Page | Query parameters |
| --- | --- |
| `/eips/{eip}/` | `fork` (occurrence), `view` (`llm`, `human`, `compare`), `rubric` (checklist revision), plus `#` anchors into criterion rows and the uncertainty section |
| `/eips/compare/` | `eips` (comma-separated, at most four), `fork` (context), `source` (`llm`, `human`, `compare`) |
| `/eips/` | `q`, `fork`, `band`, `human`, `llm`, `under`, `mode` |
| `/results/predicted-vs-observed/` | `composition=normalized` |

All pages pre-render every panel. Scripts only hide the panels the URL does not select, so the complete
content is present without JavaScript; the comparison view is the one script-dependent page and says so.

### Criterion colours

Seven criterion groups take the first seven slots of the documented categorical palette in fixed order;
members of a group are OKLCH lightness steps of the group hue. Segments carry an abbreviation, an
accessible name, and a tooltip, and every bar has a legend or table nearby, so identity never depends on
colour alone. `criteria.ts` fails the build if the payload and the registry disagree.
