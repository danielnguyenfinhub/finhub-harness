# Audit guide: rules against checks

Use this when the user asks to audit a harness or a project's rules ("audit the harness", "do our rules have checks", "which gates are real"). The audit reads and reports. It does not edit a rule, add a gate or change a setting; any fix is a separate step the user approves. (adapted from references/repository_harness/.agents/skills/onboard-repository/SKILL.md:131 and :86 and references/repository_harness/docs/patterns/encoding-invariants.md:75 and :52 (MIT), idea only, fresh text)

## 1. One row per rule or check

| rule or check | authority and source | who runs it and how | evidence class | enforcement level | finding |
|---|---|---|---|---|---|

Cite an exact path and line for the authority and for the check. A row with no path is a guess, so write `Unknown` in the finding instead.

## 2. Findings

Pick exactly one per row.

- **Enforced**: an accepted authority and a mechanical check cover the same scope.
- **Partially enforced**: the check covers only part of the accepted scope. Name the part that is not covered.
- **Unenforced rule**: an accepted authority exists and no matching check was found. A rule that lives only in prose lands here.
- **Check lacking authority**: a check exists and no accepted source establishes its policy. A code default, a test or a habit does not count as the source. An orphan gate lands here.
- **Unknown**: the evidence cannot show how the rule and the check relate.

## 3. Evidence classes

Label each claim in the table before it feeds a finding.

- **Authoritative**: an instruction, an accepted decision or a documented procedure states what must happen.
- **Observed**: code, configuration or a test shows the current behaviour.
- **Derived**: a direct consequence of something observed. Phrase it as current behaviour, not as policy.
- **Decision required**: a proposed rule has no authority yet and needs the owner's choice.
- **Unknown**: nothing in the project establishes the answer.

Never promote a class silently: an Observed, Derived, Decision required or Unknown claim does not become Authoritative because the report repeats it. In a regulated domain a default in code is not policy.

## 4. Enforcement levels

Report these apart and do not infer one from another: a local command, an optional hook, a CI invocation and branch protection. A workflow file is not a required check, and a hook the user may skip is not a gate.

## 5. Failure messages

When the audit reports a violation, or a harness check you reviewed prints one, the message names the violating item, the rule it breaks, the authority source and a compliant next action. A message that only says "failed" cannot be fixed.

## 6. Report

Open with the counts per finding, then the table, then the smallest next step for each non-Enforced row: encode an accepted rule, obtain a missing decision, or investigate an unknown. List what the audit did not look at.

## 7. Surfaces

On Claude Code the audit can run the checks and read the files. On Claude chat and Cowork there may be no shell, so run the steps by hand and mark any check you could not run as unverified.
