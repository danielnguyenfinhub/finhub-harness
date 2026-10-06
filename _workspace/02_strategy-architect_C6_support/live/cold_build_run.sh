#!/usr/bin/env bash
cd "$(dirname "$0")/project"
S=/tmp/claude-0/-home-user/cc98ae10-8075-519e-afdf-e7c3be53afa5/scratchpad/c6
timeout 900 claude -p "Read $S/skills/finhub-harness/SKILL.md and follow it step by step, reading its references/ files when it says to. Build a small harness in this directory (a project: write to ./.claude/agents, ./.claude/skills and ./CLAUDE.md) for the domain 'TODO audit': a two-agent team for Claude Code only, Mode C (sub-agent delegation): agent 'scanner' lists the TODO lines in a given text file, agent 'reporter' writes a one-page summary from the scanner's file. No connectors. Do the work through Step 6, using the lint at $S/skills/finhub-harness/scripts/lint_harness.py. Do not build the quality-gate chain. Finish by printing the lint output." --output-format stream-json --verbose --permission-mode acceptEdits --allowedTools "Bash Read Write Edit Glob Grep" --max-turns 80 < /dev/null > ../cold.jsonl 2> ../cold.err
echo done > ../cold.done
