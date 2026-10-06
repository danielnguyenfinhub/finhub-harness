#!/usr/bin/env bash
# setup_scratch.sh <repo-root> <scratch-dir>   (scratch-dir must not exist)
# Builds the layout every script here expects:  <scratch>/orig (copy of the CURRENT repo files), <scratch>/new (orig + the C7 patch),
# <scratch>/support (these scripts). Touches nothing in <repo-root>. Needs: python3, patch, jq, claude (live runs only).
set -eu
R=$(cd "$1" && pwd); T=$2; HERE=$(cd "$(dirname "$0")" && pwd)
[ -e "$T" ] && { echo "refusing to reuse $T" >&2; exit 2; }
mkdir -p "$T/orig"
for p in skills scripts tests .claude-plugin .claude CLAUDE.md README.md LICENSE NOTICE pyproject.toml; do [ -e "$R/$p" ] && cp -r "$R/$p" "$T/orig/"; done
cp -r "$T/orig" "$T/new"
(cd "$T/new" && patch -p1 < "$HERE/../02_strategy-architect_C7.patch" >/dev/null)
mkdir -p "$T/support"; cp -r "$HERE"/. "$T/support/"
bash "$T/support/proof.sh" "$T/new" >/dev/null && echo "scratch ready: $T (orig, new, support); proof.sh all OK"
