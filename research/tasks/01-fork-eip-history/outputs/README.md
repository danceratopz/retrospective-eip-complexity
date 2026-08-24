# Task 01 outputs

Each worker writes only to the paths assigned to its work unit:

```text
outputs/
├── forks/<fork-id>.yaml
├── fork-eips/<fork-id>/eip-<number>.yaml
├── eips/eip-<number>.yaml
├── sources/
│   ├── forks/<fork-id>.yaml
│   └── eips/eip-<number>.yaml
└── manifests/eip-work-units.yaml

raw/
├── forks/<fork-id>/<source-id>.<ext>
└── eips/eip-<number>/<source-id>.<ext>
```

Fork agents own their fork record, fork–EIP directory, source registry, and raw directory. EIP agents own one global EIP record, source registry, and raw directory. Only the coordinator writes the assignment manifest.

Do not place charts or combined analytical datasets here. Immutable Git sources may be referenced through repository, commit, path, and permalink. Mutable sources must be archived when redistribution permits or marked reference-only.
