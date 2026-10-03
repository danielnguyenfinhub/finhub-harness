---
name: demo-orchestrator
description: "Runs the demo team. Use for 'run the demo', 're-run the demo', 'redo only the summary'."
---

4. Connector preflight. Skip this item if the table says "none". Run it before any agent call.

   | Agent | Required connector |
   |-------|--------------------|
   | {agent} | {server, as in `mcp__{server}__*`} |
   | researcher | crm |
   | writer | crmb |

Step 1. Spawn `subagent_type: "researcher"`, then `subagent_type: "writer"`.
Use `agentType: 'general-purpose'` for one-off checks; a template shows `subagent_type: "{name}"`.
v1 migration note: remove TeamCreate and TeamDelete calls.
