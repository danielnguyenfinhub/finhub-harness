#!/usr/bin/env bash
# proof.sh <repo-root> : prints G.. rows "id got expected OK|BAD". Run from anywhere. Expected values are for the PATCHED tree.
R=${1:-.}; F=$R/skills/finhub-harness-evolve/SKILL.md; HERE=$(cd "$(dirname "$0")" && pwd)
bad=0
chk() { # chk <id> <expected> <command...>   (command prints a number)
  local id=$1 exp=$2; shift 2; local got; got=$("$@" 2>/dev/null); [ "$got" = "$exp" ] && echo "OK  $id got=$got" || { echo "BAD $id got=$got expected=$exp"; bad=1; }
}
c() { grep -c -- "$1" "$F"; }
ERE=$(bash "$HERE/ere.sh" "$F")
chk G01 1 c '^5\. \*\*Quote safely\.\*\*'
chk G02 1 c '^6\. \*\*Open the evidence before you form a lesson\.\*\*'
chk G03 1 c '^\*\*Where this runs\.\*\*'
chk G04 1 c '^\*\*Diagnose the layer first\.\*\*'
chk G05 4 c '^| \(routing\|execution\|verification\|governance\) | '
chk G06 1 c '^- Between execution and governance only: a tool error caused by a deliberate rule'
chk G07 1 c 'takes the earlier one in the order routing, execution, verification, governance, because an earlier failure explains a later one'
chk G08 1 c '^- A failure that fits no layer, or has no evidence you opened, is .unclassified.'
chk G09 1 c '^.LESSON | layer: <routing|execution|verification|governance|unclassified> | evidence: <path>:<line> - '
chk G10 1 c '^\*\*Backup gate (before the first edit)\.\*\* Before you change a harness file for the first time in this run'
chk G11 1 c 'cp -p <file> <file>.bak && cmp <file> <file>.bak'
chk G12 1 c '^5\. \*\*Check what you wrote\.\*\*'
chk G13 1 bash -c 'grep -cxF -- "   P='"'"'$1'"'"'" "$2"' _ "$ERE" "$F"
chk G14 1 c '^- Every .LESSON. line\.'
chk G15 1 c '^- Backups: for each edited file, its backup path'
chk G16 1 c '^- Secret check: what the Phase 4 grep printed'
chk G17 1 c '^Write the report to .\_workspace/evolve-report\.md. '
chk G18 9 bash -c 'grep -o "adapted from references/[^ ]* (MIT)" "$1" | wc -l' _ "$F"
chk G19 1 bash -c '[ "$(wc -l < "$1")" -lt 500 ] && echo 1' _ "$F"
chk G20 0 bash -c 'LC_ALL=C.UTF-8 grep -cP "[\x{AC00}-\x{D7A3}]" "$1"; true' _ "$F"  # rc is checked below
chk G22 0 bash -c 'grep -ciE "$2" "$1"; true' _ "$F" "$ERE"
chk G23 1 c "^   The pattern flags only what it matches\. It misses passwords of under 12 characters, "
chk G25 1 c 'Do not delete a backup yourself; tell the user that a .\.bak. left under .skills/. is packaged by'
chk G26 1 c 'the layer field holds one value'
chk G27 1 c 'a path from the project root that exists inside the project: no absolute path, no .\.\.., and never the file that holds the user'
chk G29 1 c '^- Any other failure whose evidence fits two layers (a wrong pick that a rule then blocked is routing) takes the earlier one'
chk G30 1 c '^   diff <backup> <file> | grep -niE "\$P"$'
chk G31 1 c '^   grep -niE "\$P" _workspace/evolve-report\.md$'
chk G32 1 c 'Copy it, do not retype it, and do not shorten the pattern; a shortened pattern is not this check\.'
chk G33 1 c 'then run the Phase 4 secrets command, whole, so that it greps that file'
chk G34 1 c 'A request not to open the artefacts does not waive this\.'
chk G35 1 c 'It relies on GNU .grep -E. word boundaries (BSD grep untested)\.'
chk G36 1 c 'Write each cited path in full from the project root every time you mention it, for example .\.claude/skills/<name>/SKILL\.md:17., never a bare .SKILL\.md:17.\.'
chk G24 0 bash -c 'grep -c "bearer +" "$1"; true' _ "$F"
[ "$(LC_ALL=C.UTF-8 grep -cP '[\x{AC00}-\x{D7A3}]' "$F")" = 0 ] || { echo "BAD G20b Hangul present"; bad=1; }
exit $bad
