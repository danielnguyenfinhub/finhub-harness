# QA Agent Design Guide
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

Use this guidance when you include a QA agent in a build harness. Based on bugs found in real projects and their causes, it explains how to find the defects that QA agents tend to miss.

---

## Table of Contents

1. [Patterns of defects that QA agents miss](#1-patterns-of-defects-that-qa-agents-miss)
2. [Integration coherence verification](#2-integration-coherence-verification-integration-coherence-verification)
3. [QA agent design principles](#3-qa-agent-design-principles)
4. [QA as a workflow (v2)](#4-workflow-based-qa-v2)
5. [Verification checklist template](#5-verification-checklist-template)
6. [QA agent definition template](#6-qa-agent-definition-template)
7. [Verifier stance, evidence and strategy by change type](#7-verifier-stance-evidence-and-strategy-by-change-type)

---

## 1. Patterns of defects that QA agents miss

### 1-1. Contract mismatch at component boundaries (Boundary Mismatch)

This is the most frequent defect. Each of two components is implemented correctly when viewed alone, but at the point where they connect they follow different contracts.

| Connection point | Example of mismatch | Why it is missed |
|--------|-----------|-----------|
| API response → frontend hook | The API returns `{ projects: [...] }`, but the hook expects `Project[]`. | Each component is verified alone and never compared with the other. |
| API response field names → type definition | The API uses `thumbnailUrl` (camelCase); the type uses `thumbnail_url` (snake_case). | When a type is asserted through a generic, the compiler cannot detect it. |
| File path → link `href` | The page lives at `/dashboard/create`, but the link points to `/create`. | The file structure and the `href` are never compared with each other. |
| State transition map → actual `status` update | The map defines the transition, but the code has no handling that changes the state. | The check confirms only that the map exists and does not trace the code that actually updates it. |
| API endpoint → frontend hook | The API exists, but no hook calls it. | The list of APIs and the list of hooks are never matched one to one. |
| Immediate response → asynchronous processing result | The API returns `{ status }` immediately, but the frontend accesses a final-result field. | The types are checked without distinguishing the immediate response from the final response. |

### 1-2. Why static code review alone struggles to find them

- **Limits of generic types**: With `fetchJson<Project[]>()`, the code compiles even if the actual response is `{ projects: [...] }`.
- **Why a successful build does not guarantee correct behaviour**: Code that uses type assertions, `any` or generics can build successfully and still fail at run time.
- **Whether an API exists and what its response contract is are different things to verify**: Checking "Does the API exist?" and checking "Does the API response match what the caller expects?" are entirely different tasks.

<a id="2-integration-coherence-verification-integration-coherence-verification"></a>

## 2. Integration coherence verification (Integration Coherence Verification)

A QA agent must include **verification that cross-checks components against each other**. The examples below are based on Next.js, but the principle applies to any technology stack. Open the producer code and the consumer code together and compare the contract on both sides.

### 2-1. Cross-check API responses against frontend hook types

```
1. Extract the response structure at the API route's response serialization point (NextResponse.json() and similar).
2. Check the type that the corresponding hook or client expects (the T in fetchJson<T>, and so on).
3. Compare the response structure with T. If the API returns { data: [...] }, also check that the hook extracts .data.
```

In particular, check for paginated responses wrongly received as arrays, for missing conversion between snake_case and camelCase, and for cases where the immediate response (202) and the final response have different structures.

### 2-2. Cross-check file paths against link and router paths

```
1. Extract the URL patterns from the routing file structure. Remove (group) and treat [param] as a dynamic segment.
2. Collect every href=, router.push( and redirect( value in the code.
3. Check that each link matches a path that actually exists.
```

### 2-3. Trace whether state transitions are fully implemented

```
1. Extract the list of allowed transitions from the state transition map.
2. Search for all the code that updates status.
3. Check that the transitions occurring in the code are defined in the map. There must be no disallowed transitions.
4. Find transitions that are in the map but never executed in the code. There must be no unused transitions.
5. In particular, check whether the handling that moves from an intermediate state to a final state is missing.
```

### 2-4. Match API endpoints to frontend hooks one to one

```
1. Extract the list of endpoints by HTTP method.
2. Extract the list of fetch call URLs in the client.
3. For each endpoint that is never called, decide whether it is an admin API that the client does not call directly, or whether the calling code is missing.
```

## 3. QA agent design principles

### 3-1. Choose an agent type that can use all tools

If the QA agent is of the `Explore` type, it can only read files. To do QA properly, it must be able to find patterns with `Grep`, run scripts to cross-check results automatically, and modify code if necessary. Choose `general-purpose` or a custom type that can use all tools, and state the "verify → report → request fix" procedure in the agent definition.

### 3-2. Put cross-check results in the checklist, not just existence

| Simple checklist | Cross-check-centred checklist |
|---------------|---------------|
| Does the API endpoint exist? | Does the API response structure match the type of the corresponding hook? |
| Is the state transition map defined? | Does every piece of code that updates `status` match the transition map? |
| Does the page file exist? | Does every link in the code point to a page that actually exists? |
| Is strict mode used? | Is there any place where a generic type assertion bypasses type safety? |

### 3-3. Read both sides of the connection together

To find bugs that arise at connection points, do not read the code on one side only. Read together the API route and its hook, the state transition map and the code that actually updates state, and the file structure and the link paths. State this principle clearly in the agent definition as well.

### 3-4. Run QA each time a module is completed, not after all modules are built

If QA runs only after the whole implementation is finished, bugs accumulate, fixes get more expensive, and contract mismatches introduced early spread to later modules. We recommend **incremental QA**: each time one API endpoint is completed, immediately cross-check that API against its corresponding hook.

<a id="4-workflow-based-qa-v2"></a>

## 4. QA as a workflow (v2)

If you can list the connection points to verify, you can also structure the QA process as a workflow.

```javascript
// Split the connection points and inspect them → re-verify every finding from the opposite viewpoint
const FINDINGS = { type: 'object', required: ['findings'], properties: {
  findings: { type: 'array', items: { type: 'object',
    required: ['title', 'file', 'evidence'], properties: {
      title: { type: 'string' }, file: { type: 'string' }, evidence: { type: 'string' } } } } } }
const VERDICT = { type: 'object', required: ['status', 'reason'], properties: {
  status: { type: 'string', enum: ['confirmed', 'refuted', 'uncertain'] },
  reason: { type: 'string' } } }
const boundaries = args.boundaries  // extracted by prior investigation: [{api: '...', consumer: '...'}, ...]
const found = await pipeline(
  boundaries,
  b => agent(`Read both sides together and find contract mismatches: ${b.api} ↔ ${b.consumer}`,
    { agentType: 'qa-inspector', phase: 'Inspect', schema: FINDINGS }),
  r => parallel((r?.findings ?? []).map(f => () =>
    agent(`Verify from the opposite viewpoint whether this mismatch actually causes a run-time error: ${JSON.stringify(f)}`,
      { phase: 'Re-verify', schema: VERDICT }).then(verdict => ({ ...f, verdict }))))
)
const confirmed = found.flat().filter(Boolean)
  .filter(f => f.verdict?.status === 'confirmed')
return { confirmed }
```

If you re-verify each finding from the opposite viewpoint and keep only the `confirmed` verdicts, you can filter out findings that look plausible but are not real problems. The findings in the final QA report are therefore more trustworthy.

## 5. Verification checklist template

Include the integration coherence checklist below in the definition of a QA agent that inspects a web application.

```markdown
### Integration coherence verification (web app)

#### API and frontend connection
- [ ] Check that the response structure of every API route matches the generic type of the corresponding hook.
- [ ] Check that the hook extracts the actual data value from a response wrapped in an object ({ items: [...] }).
- [ ] Check that conversion between snake_case and camelCase is applied consistently.
- [ ] Check that the frontend distinguishes the structure of the immediate response (202) from that of the final response.
- [ ] Check that every API endpoint has a corresponding frontend hook and that the hook is actually called.

#### Routing coherence
- [ ] Check that every href/router.push value in the code matches an actual page file path.
- [ ] Verify paths with the fact in mind that the (group) used for a route group is dropped from the URL.
- [ ] Check that the correct parameter value goes into each dynamic segment ([id]).

#### State machine coherence
- [ ] Check that every defined state transition is executed in the code (there must be no unused transitions).
- [ ] Check that every status update in the code is defined in the transition map (there must be no disallowed transitions).
- [ ] Check that the handling that moves from an intermediate state to a final state is not missing.
- [ ] Check that the X in each frontend state-dependent branch (if status === "X") is a state that can actually be reached.

#### Data flow coherence
- [ ] Check that the mapping between DB schema field names and API response field names is consistent.
- [ ] Check that the field names in the frontend type definitions match those in the API response.
- [ ] Check that both sides handle the null/undefined values of optional fields consistently.
```

## 6. QA agent definition template

```markdown
---
name: qa-inspector
description: "A QA agent that verifies spec compliance, integration coherence and design quality."
---

# QA agent

## Core role
Confirm that the implementation matches the spec and verify the **integration coherence between modules**.

## Verification priorities
1. **Integration coherence** (highest) — A contract mismatch at a connection point is a leading cause of run-time errors.
2. **Functional spec compliance** — Check the API, state machine and data model.
3. **Design quality** — Check colours, fonts and responsive behaviour.
4. **Code quality** — Check unused code and naming conventions.

## Verification method: read both sides of the connection together
| Verification target | Producer | Consumer |
|----------|-------|-------|
| API response structure | Response serialization point | Type the client expects |
| Routing | Routing file structure | href, router.push values |
| State transitions | Transition map | Code that updates status |
| DB → API → UI | DB table column names | API response fields → type definitions |

## Reporting and fix-request procedure
- When you find a problem, immediately ask the responsible agent for a specific fix (file:line number + how to fix it).
- If the problem arises at a connection point, notify the agents on both sides.
- Send the leader a verification report that separates passed, failed and unverified items.
```

---

## Real cases: bugs found and their causes

| Bug | Connection point | Cause |
|------|----------|------|
| `projects?.filter is not a function` | API → hook | The API returns `{projects:[]}`, but the hook expects an array. |
| A 404 occurs on every link on the dashboard | File path → `href` | The `/dashboard/` prefix is missing. |
| Thumbnail images do not appear | API → UI component | `thumbnailUrl` and `thumbnail_url` do not match. |
| The selected value is not saved | API → hook | The API exists, but there is no corresponding hook. |
| The creation page stays in the waiting state | State transition → code | The code that changes the state to the final state is missing. |
| Accessing `data.failedIndices` causes a crash | Immediate response → frontend | The frontend accesses the background processing result from the immediate response. |
| A 404 occurs when opening the detail page after completion | File path → `href` | The route prefixes do not match. |

---

## 7. Verifier stance, evidence and strategy by change type

> Adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:251 (MIT), sections cited at their own lines below. Rewritten for FinHub; the verdict rules in 7-2 deliberately differ from the source.

### 7-1. Stance

A QA agent exists to break the work, not to approve it. It fails in two predictable ways: it reads the code and writes up what it would have run instead of running it, and it passes work whose first, visible part is good (green suite, page renders) without trying the edges. Assume the orchestrator may re-run any command in your report; a passing row with no output, or output that a re-run does not reproduce, discredits the whole report. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:251-253 (MIT))

### 7-2. Evidence per check

Each check is recorded as a command plus what it printed, never as a description of code:

```markdown
| check | command | exit | output observed |
|---|---|---|---|
| CLI rejects empty input | `python -m app.cli ""` | 2 | `error: input must not be empty` |
```

A check with no command is a skip. A skipped required check makes the report FAIL. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:322 (MIT))

FinHub differences from the source, kept on purpose: the verdict is the **first** line (`RESULT: PASS` or `RESULT: FAIL`, see `quality-gates.md` §3-1), and there is no PARTIAL — a check that cannot run because a tool or service is missing is a FAIL that names what is missing.

### 7-3. Before PASS

Record at least one adversarial probe and its outcome, even if the code handled it: a boundary value, an unknown id, the same mutating call twice, two concurrent calls, or a mutation spot-check on a scratch copy (`quality-gates.md` §3-4). If every row says "exit 0" or "suite passes", only the happy path has been seen. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:312 (MIT))

### 7-4. Excuses to catch yourself making

| the thought | what goes in the report instead |
|---|---|
| "The code looks right" | A gate row: the command that exercises that code path, its exit code and its output. |
| "The builder's tests pass" | Your own `pytest -q` row, then at least one `probe:` row the builder's tests do not cover. |
| "Probably fine" | A `probe:` row aimed at the case you were unsure about. |
| "No browser / no server available" | A row showing how you looked (`which <tool>`, the session's tool list). If it is truly absent: FAIL, naming it. |
| "Too slow to check" | Start it with a time limit; if it does not finish, FAIL with the limit and the command named. |

(adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:294 (MIT))

### 7-5. Before FAIL

These checks apply only to findings outside the PASS conditions in `quality-gates.md` §3-1. For such a finding, confirm it is real before reporting FAIL:

- **Guarded elsewhere?** Open the upstream validation or downstream recovery line that would stop it.
- **Declared deliberate?** Only the design document, or a revision of it the judge has audited, counts. A deviation the builder lists in its own report does not; record that deviation as a defect for the orchestrator to accept or reject. A code comment saying "intentional" does not count either.
- **Only fixable by violating an interface that the design says an outside party owns?**

A finding set aside by any of these is still listed in the report as `observation:` with the line you opened as evidence, so it cannot disappear. None of these checks waives any PASS condition in `quality-gates.md` §3-1: a failed or skipped gate or proof command, a skipped probe, a probe whose observed behaviour differs from the design (an error-path probe that exits non-zero as designed is not a failure), a proof command with the wrong output, any boundary mismatch, a compliance-sweep hit, or a surviving non-equivalent mutant. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:315 (MIT))

### 7-6. Standing reminder

Give the QA agent a two-line reminder covering three things: read-only on the project, scratch work only in a temp directory, and the verdict format. Put it at the top of the agent file, and have the orchestrator include the same text in every QA spawn prompt so it is re-sent each time QA is started. The source declares such a reminder as a per-agent field documented as re-injected every user turn and passes it through to the host's agent field; the pinned source contains no injector of its own, and a prompt-only harness can re-send it per spawn, not per turn. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:127 and :79 (MIT))

### 7-7. Strategy by change type

Pick the row for what changed. Scale the checking to what a defect would cost: a throwaway script needs a smoke run; anything that moves money or writes a system of record gets every probe. (adapted from references/openharness/src/openharness/coordinator/agent_definitions.py:268 and :290 (MIT))

| change type | exercise it | try to break it |
|---|---|---|
| CLI or script | Run with typical arguments; check stdout, stderr and exit code; check `--help` matches behaviour | Empty, malformed and boundary arguments |
| API or server | Start it; call each changed endpoint; compare body fields with the declared contract, not only the status code | Error paths, unknown ids, the same mutating call twice |
| Library | Build, full suite, then import from a fresh interpreter and call the exported API the way a downstream user would | Exported names versus the documented ones |
| Bug fix | Reproduce the bug first, then confirm the fix and run regressions | Neighbouring behaviour for side effects |
| Refactor | Existing suite passes unchanged; public surface diff is empty | Same inputs give same outputs on a sample |
| Data pipeline | Run a sample; check schema and types | Empty input, one row, nulls; row count in versus out |
| Migration | Up, check schema, down | Run against populated data, not an empty database |
| Infrastructure or config | Validate syntax; dry-run | Every defined env var or secret is actually read |
| Frontend | Use the browser tools you have; fetch a sample of referenced assets (a page can return 200 while its assets fail) | Console errors, broken links (section 2-2) |
| **Lending, serviceability or duty calculation** (FinHub) | Recompute the expected figure by hand for a synthetic applicant from the rule the design cites | The design's threshold T and one smallest step either side (T − ε, T + ε) in the threshold's own unit (e.g. 0.01 percentage points for a ratio, one cent for an amount), rounding direction, units (monthly vs annual, % vs bps, gross vs net income). Any mismatch is FAIL unless the design states a tolerance |
| **CRM or system-of-record write** (FinHub) | Run against a stub or sandbox only, with synthetic fixtures; read the record back after writing | The same write twice (no duplicate), a write to an unknown id (explicit error), no real client data in fixtures |
| **Returns, backtest or eval scoring** (FinHub) | Apply guardrails G1-G6 in `quality-gates.md` §2-3 | A synthetic series on which a look-ahead feature would score perfectly must not |
| Anything else | Find a way to run it directly, compare with the expectation | Inputs the builder did not test |

Mobile rows from the source are not carried; no FinHub harness ships a mobile app.
