# Task 11: AI capability context for fork shipping times

## Objective

Record a measured, dated series of frontier AI capability so that the publication can offer an optional view in which each fork's predicted complexity is scaled down by the AI coding capability available when its client development began in earnest. The view is exploratory: it is display-only, off by default, and not part of any fit or result.

## Measure

METR's 50% task-completion time horizon (benchmark METR-Horizon-v1.1): the length of software task, in human working minutes, that a model completes with 50% success. It was chosen over model parameter counts, which frontier developers have not published since about 2023 and which are ambiguous for mixture-of-experts models, and over training compute, which is estimated rather than measured and is less directly about software work.

Source: <https://metr.org/assets/benchmark_results_1_1.yaml>, retrieved 2026-10-08T11:43:29Z. The file states no licence, so it is reference-only: `outputs/metr-frontier-horizon.yaml` records only the extracted model keys, release dates and horizon estimates with confidence intervals, plus the source URL, retrieval time and the file's SHA-256.

## Rule

- **Frontier at a date:** the highest 50% horizon among models released on or before that date.
- **Fork date:** the fork's first devnet with at least two independent execution-layer clients (the start of the shipping window the publication already uses), not the assessment cutoff, because AI assistance acts during implementation.
- **Hegotá:** no such devnet exists yet, so the latest measured frontier is used and labelled as a lower bound.

## Adjustment shown by the publication

adjusted complexity = complexity ÷ (1 + α · log₂(H ÷ H₀)), where H is the frontier horizon at the fork date, H₀ the earliest fork's horizon, and α the reader-chosen share of testing effort saved per doubling of horizon. α cannot be estimated from five forks; the publication lets the reader set it and refits the line on the adjusted values for display.

## Reproduce

```bash
curl -sSfL https://metr.org/assets/benchmark_results_1_1.yaml -o /tmp/metr.yaml
uv run --project research/tasks/05-retrospective-complexity-assignment --locked \
  python research/tasks/11-ai-capability-context/scripts/extract_frontier_series.py /tmp/metr.yaml --retrieved-at <UTC time>
```

A later download may differ; compare its SHA-256 with the recorded one.

## Limitations

- Horizons are measured on METR's task suite, not Ethereum client work, and client teams adopted AI tools with a lag that this measure ignores.
- The latest released model is not necessarily the one client developers used.
- gpt-3.5-turbo-instruct stands in for late-2022 and early-2023 capability; ChatGPT itself was not measured.
