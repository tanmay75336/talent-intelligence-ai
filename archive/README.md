# Archive — Development History

This directory contains earlier prototype work created during development.

The archive is preserved for historical context only. Files in this directory are **not imported, executed, or required by the final competition ranking pipeline**.

## What is here

The `prototype/` directory contains an earlier implementation path explored before the final ranking pipeline was separated into the active backend system.

It includes previous experiments around candidate processing, ranking workflows, retrieval, reasoning, storage, and system structure.

This archived implementation does not represent the current submission architecture.

## Relationship to the final system

The final solution is maintained separately in the root backend modules.

The active pipeline handles:

- candidate data processing
- ranking logic
- reasoning generation
- CSV output generation through the competition entry point

The current execution flow starts from:

```bash
python -m backend.competition.rank
```

## Active implementation

The current implementation lives outside this archive:

```text
backend/
├── competition/
├── dataset_intelligence/
├── intelligence/
├── models/
├── parsers/
├── reasoning/
└── utils/
```

Archive content is kept only as development history and is not part of the final ranking execution.
