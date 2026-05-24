# ResearchFlow Schema

Experiment records live in `.researchflow/experiments/*.json`.

Important fields:

- `id`: stable experiment ID.
- `version`: project-specific version or label.
- `kind`: `training`, `validation`, `diagnostic`, `precompute`, `lora`,
  `refiner`, `ablation`, or `experiment`.
- `status`: `planned`, `running`, `completed`, `failed`, `partial`,
  `superseded`, or `merged`.
- `parents`: direct lineage parents.
- `merged_from`: experiments combined into this experiment.
- `cites`: supporting experiments or diagnostics.
- `supersedes`: older experiments replaced by this one.
- `improves`: human-readable improvement claims.
- `regresses`: human-readable regression/tradeoff claims.
- `metrics`: scalar metrics parsed from run outputs.
- `artifacts`: paths to configs, metrics, plots, notebooks, logs, adapters, and
  other evidence.
