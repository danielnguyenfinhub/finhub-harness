#!/usr/bin/env bash
# Builds the chat skill zip and the Cowork plugin for probe P7 into dist/.
set -euo pipefail
cd "$(dirname "$0")/../../.."
src=docs/fixtures/p7-fixture-harness/.claude
out=$PWD/dist
tmp=$(mktemp -d)
mkdir -p "$out" "$tmp/skill/fixture-harness/agents" "$tmp/plugin/.claude-plugin" "$tmp/plugin/skills" "$tmp/plugin/agents"
cp "$src/skills/fixture-harness/SKILL.md" "$tmp/skill/fixture-harness/SKILL.md"
cp "$src/agents/fixture-checker.md" "$tmp/skill/fixture-harness/agents/fixture-checker.md"
cp -r "$src/skills/fixture-harness" "$tmp/plugin/skills/"
cp "$src/agents/fixture-checker.md" "$tmp/plugin/agents/"
printf '{"name":"p7-fixture-harness","version":"0.1.0","description":"Probe P7 fixture: one worker that needs a connector called fixture."}\n' > "$tmp/plugin/.claude-plugin/plugin.json"
rm -f "$out/p7-fixture-harness-skill.zip" "$out/p7-fixture-harness.plugin"
(cd "$tmp/skill" && python3 -m zipfile -c "$out/p7-fixture-harness-skill.zip" fixture-harness)
(cd "$tmp/plugin" && python3 -m zipfile -c "$out/p7-fixture-harness.plugin" .claude-plugin skills agents)
rm -rf "$tmp"
ls -l "$out"/p7-fixture-harness*
