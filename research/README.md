# Retrospective complexity research

Research is organized by task so inputs, instructions, and outputs remain separate and auditable.

```text
research/
└── tasks/
    ├── 01-fork-eip-history/
        ├── TASK.md
        ├── inputs/       # Human-approved source definitions
        ├── prompts/      # Per-fork prompts plus a reusable EIP prompt
        ├── templates/    # Required YAML output shapes
        └── outputs/      # Agent-produced research records
    ├── 02-client-implementation-history/
        ├── TASK.md
        ├── prompts/      # One reusable per-EIP agent prompt
        ├── templates/    # Input and output contracts
        └── outputs/      # One implementation record per EIP
    ├── 03-fork-development-timelines/
        ├── TASK.md
        ├── prompts/      # Reusable fresh-agent wrapper parameterized by fork
        ├── templates/    # Neutral fork-input and source-registry schemas
        ├── inputs/       # Fork milestones, devnets, and source registries
        ├── scripts/      # Reusable Altair/Vega-Lite renderer
        └── outputs/      # EL, CL, and fork-level figures
    ├── 04-complexity-assessment-ref-selection/
        ├── TASK.md
        ├── prompts/      # Minimal per-fork coordinator wrappers
        ├── templates/    # One fork–EIP ref-selection record
        └── outputs/      # Approved refs and review timelines
    ├── 04b-fork-evaluation-cutoffs/
        ├── TASK.md
        ├── templates/    # One fork cutoff/cohort record
        ├── scripts/      # Validation and review rendering
        └── outputs/      # Proposed cutoffs, cohorts, policy, and plots
    └── 05-retrospective-complexity-assignment/
        ├── TASK.md
        ├── inputs/       # Sealed one-EIP historical packages
        ├── prompts/      # One isolated-session wrapper per EIP
        ├── scripts/      # Preparation, isolation, orchestration, and validation
        └── outputs/      # Original retrospective assignments
```

YAML is the canonical research format because the records require human review, evidence notes, and occasional uncertainty. Dates must use quoted ISO 8601 values (`"YYYY-MM-DD"` or a full timestamp). Every factual claim must carry a primary-source reference.

Normalized observations reference per-work-unit source registries by source ID. Immutable Git evidence is pinned by repository, commit, path, and permalink. Mutable evidence is archived under the task's `raw/` tree with retrieval metadata and a content hash when redistribution permits; otherwise it is explicitly marked reference-only.

Task 01 first runs independently per fork, then fans out once per unique EIP to reconstruct global revision histories. Task 02 consumes the execution-layer EIP inventory from Task 01 and can run independently per unique EIP. Devnet reconstruction is intentionally handled by Task 03 because its unit of analysis is a fork/network rather than an EIP implementation.

Task 03 joins the reviewed Task 01 records with fork-level milestone and devnet participation inputs. It renders reproducible development timelines without selecting assessment dates or scoring complexity.

Task 04 consumes Task 01 inclusion events and EIP revision histories once per fork. It selects one exact historical EIP ref per execution-affecting fork–EIP relationship for later complexity assessment, without performing the assessment itself.

Task 04b consumes the approved Task 04 inventory and Task 01 fork-scope events. It freezes a separate fork-level initial evaluation horizon and partitions final EIPs into forecastable and late-scope aggregation cohorts. Every EIP is still assessed individually; cohort membership affects only fork-level totals.

Task 05 consumes only human-approved Task 04 records. It builds deterministic, hindsight-controlled historical packages and runs one isolated complexity-assessment session per EIP. Original assessments remain immutable inputs to later independent verification.
