# Quick start

## 1. Use the harness factory (recommended starting point)

First install: in Claude Code run `/plugin marketplace add danielnguyenfinhub/finhub-harness` then `/plugin install finhub-harness@finhub-harness-marketplace` (or, from a shell, `claude plugin marketplace add ...` and `claude plugin install ...`). For a small job, ask for the light mode ("build a light harness for ..."); the skill is `finhub-harness:finhub-harness-light`. For chat or Cowork, package first with `bash scripts/package-plugin.sh` (not tested on those surfaces). Then say:

```
build a harness for <your domain>
```

Examples:

- `build a harness for financial research`
- `design an agent team for code review`
- `audit this harness`

The skill will design agents, write `SKILL.md` files, and produce an orchestrator tailored to the surface you are using.

## 2. Run the Master FinHub runtime locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Run the test suite
pytest -q

# Run the CLI (scripted echo mode by default)
master-finhub "echo:hello from the runtime"
```

To use a real model, configure a profile and pass `--profile`.

## 3. Development helpers

```bash
make help          # see available commands
make test
make lint
make package       # build plugin packages for Cowork / chat
```

## 4. Reference submodules

```bash
git submodule update --init --depth 1
```

These are read-only pattern sources. See `references/LICENSES.md` before borrowing ideas.
