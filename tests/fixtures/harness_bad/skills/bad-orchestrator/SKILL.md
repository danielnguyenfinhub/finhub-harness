---
name: bad-orchestrator
description: "Runs the bad fixture team."
owner: fixtures
---

| Agent | Required connector |
|-------|--------------------|
| fetcher-two | erp |

Step 1: TeamCreate(team="old")
Step 2: pass team_name: "old" to every spawn
Step 3: TeamDelete(team="old")
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
