# prints the Phase 4 pattern exactly as shipped (the text between P=' and the closing ' inside the code fence in SKILL.md)
grep -m1 "^   P='" "${1:-skills/finhub-harness-evolve/SKILL.md}" | sed "s/^   P='//; s/'\$//"
