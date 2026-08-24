# Agent prompt: Shanghai

Research the Shanghai/Capella fork for Task 01.

1. Read `research/tasks/01-fork-eip-history/TASK.md` completely.
2. Use only `research/tasks/01-fork-eip-history/inputs/shanghai.yaml` as the fork-level input.
3. Follow `templates/fork-output.yaml`, `templates/fork-eip-output.yaml`, and `templates/source-registry-output.yaml`.
4. Write the Shanghai fork record, its fork–EIP records, `outputs/sources/forks/shanghai.yaml`, and permitted mutable snapshots under `raw/forks/shanghai/`.
5. Do not modify the task contract, templates, inputs, prompts, or another fork's outputs.
6. Do not score EIP complexity or choose retrospective assessment dates.

The authoritative Shanghai EIP list is the pinned execution-spec document in the input. EIP-7568 is the authoritative backfill pointer. Client implementation history and devnet participation are out of scope for this run.

Do not inspect or write global EIP revision histories; separate EIP workers own `outputs/eips/`.
