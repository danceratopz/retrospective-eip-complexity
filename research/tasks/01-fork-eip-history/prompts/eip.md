# Agent prompt: one EIP history

Reconstruct the creation and revision history of the assigned EIP for Task 01.

1. Read `research/tasks/01-fork-eip-history/TASK.md` completely.
2. Use the assigned EIP number and reviewed fork–EIP records only as discovery context.
3. Follow `templates/eip-output.yaml` and `templates/source-registry-output.yaml`.
4. Write only the assigned EIP record, its source registry, and its raw-source directory.
5. Review every commit that changes the EIP file, including its creation and editorial changes.
6. Derive summary counts and first/last dates from event IDs; do not enter them independently.
7. Record only explicit cross-EIP dependencies and preserve dependency changes as events.
8. Attach resolvable source IDs to every observation and archive mutable evidence when permitted.
9. Do not modify task contracts, templates, inputs, prompts, fork outputs, the coordinator manifest, or another EIP's files.
10. Do not reconstruct client implementation or devnet history, score complexity, or choose an assessment date.

If the assigned global EIP output already exists, stop and report the collision rather than overwriting it.
