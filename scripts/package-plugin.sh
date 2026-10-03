#!/usr/bin/env bash
# Validate and package the finhub-harness plugin. Run from anywhere; operates on the repo root.
# Outputs: dist/finhub-harness.plugin (Cowork), dist/finhub-harness-skill.zip and
#          dist/finhub-harness-evolve-skill.zip (Claude chat upload).
set -u
cd "$(dirname "$0")/.." || exit 1

fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

# 1. plugin.json: valid JSON, kebab-case name
manifest=.claude-plugin/plugin.json
if [ ! -f "$manifest" ]; then
  err "$manifest missing"
else
  python3 - "$manifest" <<'PY' || err "$manifest invalid (bad JSON or non kebab-case name)"
import json, re, sys
d = json.load(open(sys.argv[1]))
n = d.get("name", "")
assert isinstance(n, str) and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", n), n
PY
fi

# 2. required skills present; every skill passes the shared harness lint
#    (frontmatter, name grammar and directory, description, subagent refs, v1 artefacts)
for s in finhub-harness finhub-harness-evolve; do
  [ -f "skills/$s/SKILL.md" ] || err "skills/$s/SKILL.md missing"
done
python3 skills/finhub-harness/scripts/lint_harness.py . || err "lint_harness.py found errors (see above)"

if [ "$fail" -ne 0 ]; then echo "Validation failed; nothing packaged." >&2; exit 1; fi

# 3. package
rm -rf dist && mkdir -p dist
root=$PWD
mkzip() { # mkzip <out> <dir-to-cd> <paths...> ; excludes via -x
  out=$1; dir=$2; shift 2
  if command -v zip >/dev/null 2>&1; then
    (cd "$dir" && zip -rq "$root/$out" "$@" -x '*/.git/*' '*/_workspace*' '*/.venv/*' '*/__pycache__/*' '*.pyc')
  else
    python3 - "$root/$out" "$dir" "$@" <<'PY'
import os, sys, zipfile
out, base, *paths = sys.argv[1:]
skip = {".git", ".venv", "__pycache__"}
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in paths:
        for d, ds, fs in os.walk(os.path.join(base, p)):
            ds[:] = [x for x in ds if x not in skip and not x.startswith("_workspace")]
            for f in fs:
                if not f.endswith(".pyc"):
                    fp = os.path.join(d, f); z.write(fp, os.path.relpath(fp, base))
PY
  fi
}

inc=".claude-plugin skills"
[ -f README.md ] && inc="$inc README.md"
[ -f LICENSE ] && inc="$inc LICENSE"
[ -f NOTICE ] && inc="$inc NOTICE"
# shellcheck disable=SC2086
mkzip dist/finhub-harness.plugin . $inc
mkzip dist/finhub-harness-skill.zip skills finhub-harness
mkzip dist/finhub-harness-evolve-skill.zip skills finhub-harness-evolve

for f in dist/finhub-harness.plugin dist/finhub-harness-skill.zip dist/finhub-harness-evolve-skill.zip; do
  [ -s "$f" ] || { echo "FAIL: $f not built" >&2; exit 1; }
  printf '%s  %s bytes\n' "$f" "$(wc -c <"$f")"
done
