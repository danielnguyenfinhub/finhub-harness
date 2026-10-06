#!/usr/bin/env bash
# On-demand CodeGraph over this repo's own code, without the references/ submodules.
# Usage: scripts/codegraph.sh callers|callees|impact|query SYMBOL [options]
# Why a copy: CodeGraph has no exclude setting (only .gitignore), and ignoring references/
# would also hide it from ripgrep, which the miners rely on. The copy and index live
# outside the repo (CODEGRAPH_INDEX), so nothing here dirties the tree.
# Tool: danielnguyenfinhub/codegraph (MIT), built on first use. Needs git, node and npm.
set -euo pipefail
export NODE_NO_WARNINGS=1  # node:sqlite prints an experimental warning on every call

cd "$(git rev-parse --show-toplevel)"
home="${CODEGRAPH_HOME:-$HOME/.cache/codegraph}"
idx="${CODEGRAPH_INDEX:-$HOME/.cache/codegraph-finhub}"
cg="$home/dist/bin/codegraph.js"

if [ ! -f "$cg" ]; then
  [ -d "$home/.git" ] || git clone -q --depth 1 https://github.com/danielnguyenfinhub/codegraph "$home"
  (cd "$home" && npm ci --silent --no-audit --no-fund && npm run build --silent >/dev/null)
fi

mkdir -p "$idx"
find "$idx" -mindepth 1 -maxdepth 1 ! -name .codegraph -exec rm -rf {} +
git ls-files -co --exclude-standard -z | { grep -zv '^references/' || true; } \
  | tar --null -T - -cf - | tar -x -C "$idx"

if [ -d "$idx/.codegraph" ]; then node "$cg" sync "$idx" -q; else node "$cg" init "$idx" >/dev/null; fi

sub="${1:?usage: scripts/codegraph.sh callers|callees|impact|query SYMBOL}"
shift
node "$cg" "$sub" "$@" -p "$idx" | sed 's/\x1b\[[0-9;]*[A-Za-z]//g'
