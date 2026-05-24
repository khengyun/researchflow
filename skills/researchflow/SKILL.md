---
name: researchflow
description: Use when managing research experiments, tracing experiment lineage, comparing runs, recording prompts/states/artifacts, or closing a research session with ResearchFlow.
---

# ResearchFlow

ResearchFlow is a Codex-native workflow for experiment-first research management.
Use it before planning new experiments, after running experiments, and at the end
of a research session.

## Core Rules

- Search prior experiments before proposing a new experiment.
- Treat experiments as primary records; research states are conclusions derived
  from one or more experiments.
- Record typed lineage explicitly: `parents`, `merged_from`, `cites`,
  `supersedes`, `improves`, and `regresses`.
- Do not invent evidence. Link configs, summaries, metrics, logs, plots,
  notebooks, prompts, and artifacts that actually exist.
- At session close, scan runs, rebuild indexes, validate, and write a session
  record.

## Standard Commands

```bash
python3 -m researchflow.cli status
python3 -m researchflow.cli search "<user intent or method>"
python3 -m researchflow.cli scan
python3 -m researchflow.cli trace EXP-0001
python3 -m researchflow.cli compare EXP-a EXP-b
python3 -m researchflow.cli close-session --summary "<short session summary>"
```

If the package is installed, `rf` may be used instead.

## Workflow

1. At task start, run `status` and a targeted `search`.
2. Before proposing or launching a new experiment, find similar prior work.
3. After a run, run `scan`, then compare the new experiment against its parent
   or cited baseline.
4. When drawing conclusions, create or update a research state that cites the
   supporting experiments.
5. Before ending the session, run `close-session`.

## References

- `references/workflow.md`
- `references/schema.md`
