#!/usr/bin/env bash
# build_fixture.sh <template.md> <variant: good|once|always> <outdir> [noblock]
# Builds a runnable Mode C fixture: .claude/agents/scanner.md (test double), .claude/skills/fixture-orchestrator/SKILL.md
# (the Delegation block extracted from the template by awk, so the live test uses the shipped text), _workspace/note.txt.
set -eu
T=$1; V=$2; OUT=$3; HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT/.claude/agents" "$OUT/.claude/skills/fixture-orchestrator" "$OUT/_workspace"
cp "$HERE/variants/$V.md" "$OUT/.claude/agents/scanner.md"
echo "fixture line one" > "$OUT/_workspace/note.txt"
awk '/^````markdown/{f=1;next} /^````$/{f=0} f' "$T" > "$OUT/block.md"
{
cat <<'HEAD'
---
name: fixture-orchestrator
description: "Runs the fixture harness. Use for 'run the fixture harness', 're-run the fixture harness'."
---

# Fixture orchestrator

## Execution mode: Sub-agent delegation (Mode C), Claude Code only

### Step 1: Preparation
Create `_workspace/` if missing.

### Step 2: Launch
Launch one `Agent` call with `subagent_type: "scanner"`, no `name`, run in the foreground. Brief it with:
Goal: say the status of the fixture, for the test log.
Inputs: none.
Scope: no tools; write nothing.
Expected output: your reply only.
Report: as below.

HEAD
if [ "${4:-}" = noblock ]; then echo "Report: end with a one-line status."; else cat "$OUT/block.md"; fi
echo
echo "### Step 3: Integrate"
if [ "${4:-}" = noblock ]; then echo 'Give the user one line: `RESULT: accepted` or `RESULT: unverified`, followed by the status you recorded.'
else echo 'Apply the Check before use rule to the scanner report, then give the user one line: `RESULT: accepted` or `RESULT: unverified`, followed by the status you recorded.'; fi
} > "$OUT/.claude/skills/fixture-orchestrator/SKILL.md"
cat > "$OUT/run.sh" <<'RUN'
#!/usr/bin/env bash
# run.sh <tag>  : one live run, no bypassPermissions
cd "$(dirname "$0")"
timeout 250 claude -p "run the fixture harness" --output-format stream-json --verbose --permission-mode dontAsk \
  --allowedTools "Agent Read Skill SendMessage Write" --max-turns 10 < /dev/null > "$1.jsonl" 2> "$1.err"
RUN
chmod +x "$OUT/run.sh"
