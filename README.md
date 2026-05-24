# ResearchFlow

ResearchFlow is a Codex-native plugin for managing research experiments as local, Git-friendly records. It is agent-first: Codex can scan experiment runs, search prior work, trace lineage, compare experiments, and close sessions into `.researchflow/`.

## What It Tracks

- Experiments and run artifacts
- Derived, merged, cited, superseded, improved, and regressed relationships
- Metrics, configs, summaries, logs, plots, notebooks, prompts, and states
- Session records created by an agent after work is done

## CLI

```bash
python3 -m researchflow.cli init
python3 -m researchflow.cli scan
python3 -m researchflow.cli status
python3 -m researchflow.cli search "log residual"
python3 -m researchflow.cli build-vector-index
python3 -m researchflow.cli similar "failed lora ablation"
python3 -m researchflow.cli trace EXP-abc123
python3 -m researchflow.cli compare EXP-a EXP-b
python3 -m researchflow.cli close-session --summary "Finished v0.5 ablation review"
```

The default project root is the current directory. Use `--root /path/to/repo` for another repo.

## Codex Plugin Development

This repository is itself the plugin root. For local Codex testing, create a marketplace in another repo:

```json
{
  "name": "local",
  "interface": {
    "displayName": "Local"
  },
  "plugins": [
    {
      "name": "researchflow",
      "source": {
        "source": "local",
        "path": "./plugins/researchflow"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

After installing/enabling the plugin in Codex, verify:

- `/mcp` shows `researchflow`
- `/hooks` shows the hook scripts if hooks are configured/trusted by the host
- Asking Codex about research experiments triggers the `researchflow` skill

## Data Store

ResearchFlow writes only under the target repo by default:

```text
.researchflow/
  .gitignore
  project.json
  experiments/
  states/
  prompts/
  sessions/
  indexes/
```

JSON is the guaranteed format. YAML files are read if `PyYAML` is available.

## Semantic Search

ResearchFlow can add a local semantic index over experiment records only. The
experiment JSON remains the source of truth; ChromaDB is a rebuildable cache
stored under `.researchflow/indexes/chroma/`.

Install optional dependencies:

```bash
pip install "researchflow[vector]"
```

Build or refresh the index:

```bash
python3 -m researchflow.cli build-vector-index
```

Search semantically:

```bash
python3 -m researchflow.cli similar "experiments that improved validation MAE but regressed edges"
```

Codex hooks try semantic search on each user prompt and fall back to lexical
`search` when the vector dependencies or index are unavailable.
