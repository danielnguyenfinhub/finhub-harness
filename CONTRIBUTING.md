# Contributing to finhub-harness

Thank you for your interest in improving finhub-harness.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e '.[dev]'
pre-commit install   # optional but recommended
```

Run the test suite:

```bash
make test
# or
pytest -q
```

Lint and type-check:

```bash
make lint
make typecheck
```

## Project structure

- `skills/finhub-harness/` — the main harness factory skill
- `src/master_finhub/` — the pure-Python agent runtime
- `.claude/` — the six-agent build team that maintains the runtime
- `references/` — pinned read-only submodules of other harnesses (pattern mining only)
- `docs/` — additional documentation

## Licence rules

When proposing changes that draw from the reference submodules:

1. Cite the source (`references/<repo>/<path>:<line>`) and licence tier.
2. Prefer patterns over verbatim copies.
3. Respect the hard stops listed in `references/LICENSES.md`.
4. Expect the Authority List + fresh-context judge process.

## Pull requests

- Open a PR against `main`.
- Keep commits focused.
- Make sure CI passes (`ruff`, `black`, `mypy`, `pytest`).
- Update relevant documentation and the changelog if the change is user-visible.

## Agent-team workflow

The runtime and many of the skills were built by the agents in `.claude/`. You can ask the `master-finhub-orchestrator` skill to rebuild or extend slices. See `CLAUDE.md` for the current operating conventions.
