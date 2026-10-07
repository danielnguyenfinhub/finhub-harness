#!/usr/bin/env bash
# Deterministic cross-reference check for the master-finhub team prose.
# Exit 0 = every check passed; exit 1 = at least one FAIL line printed.
set -u
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"  # resolved before the cd below
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

# 3. nine miner submodules named in the orchestrator (the phase table uses {submodule})
for m in autogpt openhands dify crewai deepseek_harness revfactory_harness openharness meta_harness openrig; do
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

# 9. reference pins: .gitmodules is the source of truth for the nine-pin documents
GM=.gitmodules; L=references/LICENSES.md; LR=$S/reference-mining/references/licence-rules.md; SE=skills/finhub-harness/references/source-enrichment.md
subs=$(git config -f $GM --get-regexp '^submodule\..*\.path$' | awk '{print $2}' | sed 's|^references/||')
nsub=$(echo "$subs" | wc -l)
numw=(zero one two three four five six seven eight nine ten eleven twelve)
row() { grep -E "^\| \`$2\` \|" "$1" | head -1; }   # row <file> <name>
cell() { row "$1" "$2" | awk -F'|' -v n="$3" '{gsub(/^ +| +$/,"",$n); print $n}'; }   # cell <file> <name> <3 upstream|4 licence>
pinstr() { row "$1" "$2" | grep -oE 'Pinned [0-9-]+ at [0-9a-f]{7,40}'; }
gitlink() { # full sha from index, else HEAD, else the checkout's own HEAD; empty when none is available
  local p=references/$1 s
  s=$(git ls-files -s -- "$p" | awk '$1=="160000"{print $2}')
  [ -z "$s" ] && s=$(git ls-tree HEAD -- "$p" 2>/dev/null | awk '$1=="160000"{print $3}')
  [ -z "$s" ] && [ -e "$p/.git" ] && s=$(git -C "$p" rev-parse HEAD 2>/dev/null)
  echo "$s"
}
pins_ok() { # stated sha is a prefix of the gitlink in every doc that states one; one identical "Pinned DATE at SHA" across docs
  local m=$1 full ref="" p f
  full=$(gitlink "$m")
  for f in $L $LR $SE; do
    p=$(pinstr "$f" "$m"); [ -z "$p" ] && continue
    [ -n "$ref" ] && [ "$p" != "$ref" ] && return 1
    ref=$p
    [ -n "$full" ] && [[ $full != "${p##* }"* ]] && return 1
  done
  return 0
}
lic_ok() { # licence cell (plain Apache-2.0 or MIT rows only) matches the LICENSE file
  local m=$1 c f=references/$1/LICENSE kind
  c=$(cell $L "$m" 4); [[ $c =~ ^(Apache-2\.0|MIT)( \(|$) ]] || return 0
  [ -f "$f" ] || return 0
  if grep -q 'Apache License' "$f"; then kind=Apache-2.0; elif grep -qE 'MIT License|Permission is hereby granted' "$f"; then kind=MIT; else return 1; fi
  [ "${BASH_REMATCH[1]}" = "$kind" ]
}
upstream_ok() { # urls outside the fork org are "upstream": the licence row names that repo, and each doc's fork sentence lists exactly them
  local m url up="" f line
  for m in $subs; do
    url=$(git config -f $GM "submodule.references/$m.url")
    if [[ $url == *github.com/danielnguyenfinhub/* ]]; then continue; fi
    up="$up $m"; [ "$(cell $L "$m" 3)" = "$(echo "$url" | sed 's|.*github.com/||; s|\.git$||')" ] || return 1
  done
  for f in $L $LR $SE; do
    line=$(grep -m1 'pin the upstream' "$f") || return 1
    for m in $subs; do
      if [[ " $up " == *" $m "* ]]; then [[ $line == *"\`$m\`"* ]] || return 1; else [[ $line != *"\`$m\`"* ]] || return 1; fi
    done
  done
}
count_ok() { # the file states $nsub (digit or word) before pinned/reference/port maps, and no other count (bare "one" exempt: "mines ONE pinned submodule"); history rows (| 20..) are exempt
  local f=$1 w=${numw[$nsub]} i bad="" body
  for i in $(seq 2 12); do [ "$i" -ne "$nsub" ] && bad="$bad|${numw[$i]}|$i"; done
  body=$(grep -v '^| 20' "$f")
  echo "$body" | grep -qiE "\b($w|$nsub) (pinned|reference|port maps?|maps)" &&
    ! echo "$body" | grep -iE "\b(${bad#|}) (pinned|reference|port maps?)"
}
loop_ok() { [ "$(sed -n '/^# 3\./,/^done/{s/^for m in \(.*\); do$/\1/p}' "$SELF" | tr ' ' '\n' | sort)" = "$(echo "$subs" | sort)" ]; }
chk "submodule count 1..12" test "$nsub" -ge 1 -a "$nsub" -le 12
chk "miner loop covers .gitmodules" loop_ok
for m in $subs; do
  chk "LICENSES row $m" test -n "$(row $L "$m")"
  chk "shallow $m" test "$(git config -f $GM "submodule.references/$m.shallow")" = true
  chk "pin sha+date $m" pins_ok "$m"
  chk "licence file $m" lic_ok "$m"
done
chk "every LICENSES row is a submodule" bash -c "! grep -oE '^\| \`[a-z_]+\` \|' $L | tr -d '|\` ' | grep -vxF '$subs'"
chk "upstream vs fork wording" upstream_ok
for f in README.md CLAUDE.md $O $A/capability-scout.md $A/strategy-architect.md $A/reference-miner.md; do
  chk "pin count ${numw[$nsub]} in $f" count_ok "$f"
done
chk "fan-out x$nsub in miner" grep -q "fanned out x$nsub " $A/reference-miner.md
chk "orchestrator 'up to ${numw[$nsub]} Agent' calls" grep -qF "up to ${numw[$nsub]} \`Agent\`" $O
for f in $O $S/master-finhub-orchestrator/references/phase-table.md $A/capability-scout.md; do
  chk "fan-out ×$nsub in $f" grep -q "reference-miner ×$nsub" "$f"
done

# 10. packager
chk "packager exit 0" bash scripts/package-plugin.sh

exit $fail
