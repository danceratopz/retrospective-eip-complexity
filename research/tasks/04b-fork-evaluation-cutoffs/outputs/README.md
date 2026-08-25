# Task 04b outputs

`forks/<fork>.yaml` is the canonical proposed cutoff and aggregation-cohort record. `aggregation-policy.yaml` defines how later fork reports use those cohorts without changing original EIP assessments.

Validate all records from the repository root:

```bash
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04b-fork-evaluation-cutoffs/scripts/validate_outputs.py
```

Render the cutoff over the approved Task 04 EL review timelines:

```bash
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04b-fork-evaluation-cutoffs/scripts/render_review.py --validate-only
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04b-fork-evaluation-cutoffs/scripts/render_review.py
```

Generated review artifacts must not be edited by hand. A cutoff record remains proposed until the project owner explicitly approves it.
