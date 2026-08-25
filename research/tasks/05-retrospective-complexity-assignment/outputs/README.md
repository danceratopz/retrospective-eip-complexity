# Task 05 outputs

One original assessment is stored at `fork-eips/<fork-id>/eip-<number>.yaml`. Assessors must start from the generated package template and may write only their assigned output.

Validate one output from the repository root with:

```bash
uv run --project research/tasks/05-retrospective-complexity-assignment --locked python research/tasks/05-retrospective-complexity-assignment/scripts/validate_output.py --fork FORK --eip NNNN
```

Verifier results belong to a later task and must not overwrite these files.
