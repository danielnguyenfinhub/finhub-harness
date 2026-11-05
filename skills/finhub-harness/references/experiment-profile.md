# Experiment profile: harnesses that try changes and keep the winners

Use this when the user wants a harness that repeatedly changes something and measures the result ("optimise this prompt", "tune these thresholds", "find which team layout works better"). It is a profile layered on a Pipeline, Supervisor or Producer-Reviewer team from `team-patterns.md`. It is not a seventh pattern, so the team patterns stay six. (adapted from references/meta_harness/.agents/skills/harness/references/autonomous-experimentation.md:23-33 and :85-91 and references/meta_harness/.agents/skills/harness/references/skill-testing-guide.md:184-202 (Apache-2.0), idea only, fresh text; the effect-size rule follows references/revfactory_harness/README.md:259 (Apache-2.0))

## 1. When not to use it

Refuse the profile and say why when any of these holds:

- the evaluation surface is still changing during the same loop;
- the mutable surface is so broad that undoing a failed idea is unclear;
- there is no declared metric or comparison rule;
- a crash, a timeout or a half-finished run would cause production side effects;
- the run happens somewhere the user cannot audit.

## 2. The contract: seven items, named before the first candidate

The generated orchestrator writes all seven, and the user sees them, before any candidate runs.

1. **Mutable surface**: the files, parameters, prompts or scripts a candidate may change, and nothing else.
2. **Read-only evaluation surface**: the code, data, rubric or benchmark that stays untouched for the whole run.
3. **Baseline run**: one measured run before any change.
4. **Comparison rule**: the fixed budget, dataset or prompt set that every candidate is measured against.
5. **Experiment ledger**: one file under `_workspace/experiments/<run>/` (or one `unit_tracker.py` table, `unit-tracker.md`).
6. **Keep/discard rule**: when a change is kept, when it is undone and when it is retried.
7. **Failure rule**: how many retries, what counts as a timeout, and what happens after a crash.

The evaluation surface is read-only for the run. If it has to change, that starts a new run with a new baseline, and scores from before the change are not compared with scores after it.

## 3. The ledger

One row per candidate: an id, the metric, the run time, a status (`keep`, `discard`, `crash` or `timeout`) and a one-line summary. The baseline is row one. A crashed or timed-out candidate stays in the ledger; it is never deleted to tidy the table.

## 4. The loop

1. Snapshot the request and the starting state.
2. Measure the baseline.
3. Make one bounded candidate: one change inside the mutable surface.
4. Run it under the budget.
5. Log it at once, before deciding anything. This is what lets a resumed run continue instead of starting again.
6. Decide by the keep/discard rule.
7. Summarise: what was kept, what was discarded and what was not tried.

## 5. Failures

Retry only mechanical failures (a flaky download, a full disk), one or two attempts. A timeout or a crash caused by the candidate itself is not retried to make the number look better: it is a result, and it stays in the ledger. A step with an outside effect is not an experiment: use the run-once rules of `state-ledger.md` and the Ask-first block of `orchestrator-template.md` instead.

## 6. Comparing two team layouts

To compare an old and a proposed way of delegating, use the same task fixture and snapshot, the same model family and permissions, the same budget and output contract, and the same acceptance checks and rubric. Start with four paired scenarios:

1. a small near-miss that should stay direct and leave no durable files;
2. a read-heavy review with independent branches and one owner for the synthesis;
3. a write-heavy task that must refuse overlapping writes or separate them by owner;
4. a failure case with one missing branch and conflicting findings, which must keep the uncertainty.

Run one pair first and repeat only a tie or an odd result. Hide which side is current and which is proposed from whoever compares them when you can.

## 7. Gates before the score

Check the hard gates first: nothing that was meant to stay untouched changed, no two workers wrote the same file, every output has a named owner, gaps are disclosed and no evidence is invented. Then score. A high score cannot buy back a failed gate. Call a result high-confidence only when every gate passes, correctness holds, the target improves in more than one case and the near-miss case does not get worse; otherwise write it up and defer it.

## 8. Reporting a result

State the limit in the report: a handful of paired runs is a pilot, not a statistical test. Any claim about the size of an effect carries its sample size and who measured it ("n=15, author-measured"), and tells the reader to run their own pilot before relying on it.
