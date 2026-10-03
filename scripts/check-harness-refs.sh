#!/usr/bin/env bash
# Deterministic cross-reference check for the master-finhub team prose.
# Exit 0 = every check passed; exit 1 = at least one FAIL line printed.
set -u
cd "$(dirname "$0")/.."
fail=0
chk() { # chk <description> <command...>
  local d=$1; shift
  if "$@" >/dev/null 2>&1; then echo "PASS $d"; else echo "FAIL $d"; fail=1; fi
}
all() { local p=$1; shift; for f in "$@"; do grep -qE -- "$p" "$f" || return 1; done; }  # pattern in every file

A=.claude/agents; S=.claude/skills
O=$S/master-finhub-orchestrator/SKILL.md

# 1. agents: frontmatter name/description/model, and a "Not for" clause
for f in $A/*.md; do
  n=$(basename "$f" .md)
  chk "frontmatter $n" bash -c "head -1 '$f' | grep -q '^---\$' && grep -q '^name: $n\$' '$f' && grep -q '^description: ' '$f' && ! grep -E '^model:' '$f' | grep -vqE '^model: (opus|sonnet)'"
  chk "Not-for clause $n" bash -c "grep -m1 '^description:' '$f' | grep -q 'Not for'"
done

# 2. skills: frontmatter name matches directory
for d in $S/*/; do
  n=$(basename "$d")
  chk "skill frontmatter $n" grep -q "^name: $n\$" "$d/SKILL.md"
done

# 3. seven miner submodules named in the orchestrator (the phase table uses {submodule})
for m in autogpt openhands dify crewai deepseek_harness revfactory_harness openharness; do
  chk "miner $m in orchestrator" all "$m" $O
done

# 4. adoption verdict path variant in every file that names the verdict file
chk "verdict path _r<k>" all '_r<k>' $S/adversarial-audit/SKILL.md $S/adversarial-audit/references/verdict-schema.md $A/adversarial-risk-judge.md $O

# 5. extra-round authorisation recorded end to end
chk "authorisation line" all 'Extra round authorised by Daniel' $S/adversarial-audit/SKILL.md $S/adversarial-audit/references/verdict-schema.md $O
chk "judge agent authorisation" all 'authorisation' $A/adversarial-risk-judge.md

# 6. Deferred section defined everywhere the backlog layout is
chk "Deferred section" all '## Deferred' $A/capability-scout.md $S/capability-triage/SKILL.md
chk "Deferred pick rule" all 'Deferred' $O

# 7. every agent in the team exists as a file; CLAUDE.md says six and six files exist
for n in reference-miner capability-scout strategy-architect adversarial-risk-judge runtime-builder boundary-qa; do
  chk "agent file $n" test -f "$A/$n.md"
done
chk "six agent files" test "$(ls $A/*.md | wc -l)" -eq 6
chk "CLAUDE.md says six-agent" grep -q 'six-agent' CLAUDE.md

# 8. no Hangul in agents or the triage skill (Korean phase markers in the orchestrator are the repo's convention)
chk "no Hangul in agents+triage" bash -c "LC_ALL=C.UTF-8 grep -rP '[\x{AC00}-\x{D7A3}]' $A $S/capability-triage; test \$? -eq 1"

# 9. packager
chk "packager exit 0" bash scripts/package-plugin.sh

exit $fail
