#!/usr/bin/env bash
# check_case.sh <good|once|always|noblock-always> <run.jsonl>   prints PASS or FAIL with the numbers.
# Rules: good = 1 worker call, final accepted. once = 2 calls, final accepted. always = exactly 2 calls AND a final line AND
# (final says unverified, OR the second reply's EVIDENCE line is non-empty). noblock-always (control) must NOT be 2 calls.
J=$2
calls=$(jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | .name' "$J" | grep -cE '^(Agent|SendMessage)$' || true)
final=$(jq -r 'select(.type=="result") | .result // empty' "$J" | head -3 | tr '\n' ' ')
lastev=$(jq -r 'select(.type=="user") | .message.content[]? | select(.type=="tool_result") | (.content | if type=="array" then map(.text? // "") | join("") else . end)' "$J" | grep -E '^\s*EVIDENCE:' | tail -1 | sed 's/^\s*EVIDENCE:\s*//')
ok=0
case $1 in
  good)   [ "$calls" = 1 ] && echo "$final" | grep -qi '^RESULT: accepted\|^accepted\|RESULT: accepted' && ok=1 ;;
  once)   [ "$calls" = 2 ] && echo "$final" | grep -qi 'accepted' && ok=1 ;;
  always) [ "$calls" = 2 ] && [ -n "$final" ] && { echo "$final" | grep -qi 'unverified' || [ -n "$lastev" ]; } && ok=1 ;;
  noblock-always) [ "$calls" != 2 ] && ok=1 ;;
esac
echo "$([ $ok = 1 ] && echo PASS || echo FAIL) case=$1 worker_calls=$calls last_EVIDENCE='$lastev' final='${final:0:90}'"
