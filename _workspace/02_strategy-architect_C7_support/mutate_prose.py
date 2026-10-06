"""mutate_prose.py [ids...]: one fresh process per mutant. Each mutant edits the patched SKILL.md (asserting the old text occurs exactly
once and the file really changed), then runs three checks as separate subprocesses:
  pins       pins.py        whole-file text freeze (PRESENCE: it kills every textual change by construction, so it proves a sentence exists)
  greps      proof.sh       the G.. grep rows (PRESENCE)
  behaviour  ere_tests.py   the shipped pattern run on positives and negatives (BEHAVIOUR of the pattern)
A mutant is KILLED when any exits non-zero. The report separates mutants killed by a behaviour check from those killed only by presence checks.
Live behaviour kills (layer, backup, existing backup, evidence, secret via G) are in the live runs, not here (see the design)."""
import subprocess, sys, tempfile, shutil
from pathlib import Path
here = Path(__file__).resolve().parent
SK = here.parent / "new/skills/finhub-harness-evolve/SKILL.md"
base = SK.read_text(encoding="utf-8")
ERE = subprocess.run(["bash", str(here / "ere.sh"), str(SK)], capture_output=True, text=True).stdout.strip("\n")
out = []  # (id, group, rule, old, new)
def m(i, g, rule, old, new): out.append((i, g, rule, old, new))
def span(start, end):  # the text from start through end (inclusive)
    s = base.index(start); e = base.index(end, s) + len(end); return base[s:e]
# ---- layer rule
for i, row in enumerate(["| routing | the wrong skill", "| execution | a step ran", "| verification | an output was produced", "| governance | a rule, gate"]):
    m(f"LAY{i+1}", "layer", "layer table row deleted", span(row, "\n"), "")
m("LAY5", "layer", "execution/governance rule inverted", "is governance, not execution.", "is execution, not governance.")
m("LAY6", "layer", "execution/governance bullet deleted", span("- Between execution and governance only:", "\n"), "")
m("LAY6b", "layer", "execution/governance scope removed (rule applies to every pair)", "- Between execution and governance only: a tool error", "- Always: a tool error")
m("LAY7", "layer", "tie order reversed", "in the order routing, execution, verification, governance, because", "in the order governance, verification, execution, routing, because")
m("LAY8", "layer", "tie: earlier -> later", "takes the earlier one in the order", "takes the later one in the order")
m("LAY9", "layer", "tie bullet deleted", span("- Any other failure whose evidence fits two layers", "\n"), "")
m("LAY9b", "layer", "tie: routing example removed", " (a wrong pick that a rule then blocked is routing)", "")
m("LAY10", "layer", "one-lesson-per-failure sentence removed", "Write one lesson line per failure and put \"also: <other layer>\" at the end of that same line, never on a second line; the layer field holds one value.", "")
m("LAY11", "layer", "unclassified bullet deleted", span("- A failure that fits no layer, or has no evidence", "\n"), "")
m("LAY12", "layer", "unclassified: edit nothing removed", ", and edit nothing for it.", ".")
m("LAY13", "layer", "unclassified: no-evidence arm removed", "A failure that fits no layer, or has no evidence you opened, is", "A failure that fits no layer is")
m("LAY14", "layer", "exactly one -> at least one", "put each failure in exactly one layer", "put each failure in at least one layer")
m("LAY15", "layer", "format: layer field dropped", "`LESSON | layer: <routing|execution|verification|governance|unclassified> | evidence:", "`LESSON | evidence:")
m("LAY16", "layer", "format: evidence field dropped", "| evidence: <path>:<line> - <what in that line supports the lesson> |", "|")
m("LAY17", "layer", "format: fix none rule removed", "Use `fix: none` for an `unclassified` lesson. ", "")
m("LAY18", "layer", "format: layer set widened", "<routing|execution|verification|governance|unclassified>", "<routing|execution|verification|governance|unclassified|other>")
m("LAY19", "layer", "layer step: evidence reference removed", ", using the evidence from Phase 1 step 6", "")
# ---- evidence rule
m("EV1", "evidence", "opened in this run removed", "cites `path:line` of a file you opened in this run and says", "cites `path:line` of a file and says")
m("EV2", "evidence", "missing-instruction sentence removed", " A missing instruction is evidenced by the file that should hold it plus a search that finds nothing (`grep -c` printing 0).", "")
m("EV3", "evidence", "symptom sentence removed", " The user's words are the symptom, not the evidence: record them as the symptom, then find the file.", "")
m("EV4", "evidence", "no-file lesson: unclassified -> applied", "A lesson with no such file is `unclassified` (Phase 2).", "A lesson with no such file is still applied.")
m("EV5", "evidence", "point-in-time sentence removed", " A note or memory from an earlier run is a point-in-time claim until you re-open its file.", "")
m("EV6", "evidence", "path:line -> path", "cites `path:line` of a file", "cites `path` of a file")
m("EV7", "evidence", "what-supports removed", " and says what in that line supports it", "")
m("EV8", "evidence", "step 6 deleted", span("6. **Open the evidence before you form a lesson.**", "\n"), "")
m("EV9", "evidence", "project-path / no .. / no feedback file sentence removed", " Every `path:line` you cite is a path from the project root that exists inside the project: no absolute path, no `..`, and never the file that holds the user's feedback.", "")
m("EV10", "evidence", "'asked not to open' sentence removed", " A request not to open the artefacts does not waive this.", "")
m("EV11", "evidence", "feedback file allowed", ", and never the file that holds the user's feedback.", ".")
m("EV12", "evidence", "full-path-every-time sentence removed", " Write each cited path in full from the project root every time you mention it, for example `.claude/skills/<name>/SKILL.md:17`, never a bare `SKILL.md:17`.", "")
# ---- backup rule
m("BK1", "backup", "gate deleted", span("**Backup gate (before the first edit).**", "\n\n"), "")
m("BK2", "backup", "before -> after first edit", "Before you change a harness file for the first time in this run, copy it", "After you change a harness file for the first time in this run, copy it")
m("BK3", "backup", "cmp dropped", "`cp -p <file> <file>.bak && cmp <file> <file>.bak`", "`cp -p <file> <file>.bak`")
m("BK4", "backup", "existing .bak overwritten", "If `<file>.bak` already exists, leave it alone (it may be the only copy from before an earlier evolve) and use the first unused `<file>.bak.2`, `<file>.bak.3` and so on.", "If `<file>.bak` already exists, overwrite it.")
m("BK5", "backup", "one per file per run -> per edit", "One backup per file per run, taken before that run's first edit to it;", "One backup per edit;")
m("BK6", "backup", "fail-closed sentence removed", " If the copy fails or `cmp` prints anything, edit nothing and say so.", "")
m("BK7", "backup", "new-file sentence removed", " a file you create has no backup and is listed as new.", "")
m("BK8", "backup", "cp -p -> mv", "`cp -p <file> <file>.bak && cmp", "`mv <file> <file>.bak && cmp")
m("BK9", "backup", ".bak suffix changed", "`cp -p <file> <file>.bak && cmp <file> <file>.bak`", "`cp -p <file> <file>.orig && cmp <file> <file>.orig`")
m("BK10", "backup", "Phase 4 backups check deleted", span("   - Backups: `ls <file>.bak*`", "\n"), "")
m("BK11", "backup", "Phase 5 backups bullet deleted", span("- Backups: for each edited file, its backup path", "\n"), "")
m("BK12", "backup", "undo command removed", " To undo a change: `cp <file>.bak <file>`.", "")
m("BK13", "backup", "cmp result removed from report", " and the `cmp` result taken before the edit", "")
m("BK14", "backup", "Phase 4 'differ' -> 'match'", "says the two now differ.", "says the two now match.")
m("BK15", "backup", "packaging warning removed", " Do not delete a backup yourself; tell the user that a `.bak` left under `skills/` is packaged by `scripts/package-plugin.sh`, so it should go once the change is accepted.", "")
# ---- secret rule
m("SEC1", "secret", "step 5 intro sentence removed", " A prose rule cannot guarantee that none leaks; this one lowers the risk and the check in Phase 4 looks at what you wrote.", "")
for i, shape in enumerate(["an `sk-`, `sk_live_`, `ghp_`, `github_pat_`, `xox` or `AIza` prefix", "`AKIA` plus 16 characters", "a `Bearer` or `Basic` credential", "a private-key block", "a JWT (`eyJ` and two dotted segments)", "the value after `api_key=`, `secret_key=`, `token=`, `secret=` or `password=`", "or a URL with `user:password@`"]):
    m(f"SEC2.{i+1}", "secret", "shape removed from the list", shape, "")
m("SEC3", "secret", "never-copy bullet deleted", span("   - Never copy one into a lesson", "\n"), "")
m("SEC4", "secret", "redaction wording keeps first 4", "Replace the whole value with `[REDACTED:<kind>]` (`api-key`, `bearer`, `private-key`, `jwt`, `password` or `credential-url`), keeping no first or last characters, no length and no hash.", "Replace the value with `[REDACTED:<kind>]`, keeping its first four characters.")
m("SEC5", "secret", "no-first-last clause removed", ", keeping no first or last characters, no length and no hash", "")
m("SEC6", "secret", "cite-instead-of-quote removed", " Cite the file and line instead of quoting the line.", "")
m("SEC7", "secret", "Not-secrets bullet deleted", span("   - Not secrets:", "\n"), "")
m("SEC8", "secret", "when-unsure-redact removed", " When unsure, redact; the cost is a less specific lesson.", "")
m("SEC9", "secret", "other-credential sentence removed", " Treat any other string the user calls a credential the same way.", "")
m("SEC10", "secret", "Phase 4 secrets bullet deleted", span("   - Secrets: once the report file exists", "\n\n"), "")
m("SEC11", "secret", "-niE -> -nE (added-lines grep)", "   diff <backup> <file> | grep -niE \"$P\"", "   diff <backup> <file> | grep -nE \"$P\"")
m("SEC11b", "secret", "-niE -> -nE (report grep)", "   grep -niE \"$P\" _workspace/evolve-report.md", "   grep -nE \"$P\" _workspace/evolve-report.md")
m("SEC12", "secret", "'any output is a leak' -> 'ignore output'", "Any output is a leak: redact it and run the command again.", "Any output is a false alarm: ignore it.")
m("SEC13", "secret", "report-grep line deleted", span("   grep -niE \"$P\" _workspace/evolve-report.md", "\n"), "")
m("SEC13b", "secret", "added-lines grep line deleted", span("   diff <backup> <file> | grep -niE \"$P\"", "\n"), "")
m("SEC14", "secret", "limits paragraph removed", span("   The pattern flags only what it matches.", "does not remove it."), "")
m("SEC14b", "secret", "limits: 'misses' list removed", "It misses passwords of under 12 characters, `Bearer` followed by two spaces or a tab, Twilio `AC` SIDs, Slack webhook URLs, base64 blobs and a secret split over two lines, and it flags", "It flags")
m("SEC14c", "secret", "limits: final-message-not-grepped removed", " The final chat message is not grepped.", "")
m("SEC14d", "secret", "limits: GNU sentence removed", " It relies on GNU `grep -E` word boundaries (BSD grep untested).", "")
m("SEC15", "secret", "Phase 5 intro (write then grep whole) deleted", span("Write the report to `_workspace/evolve-report.md`", "\n\n"), "")
m("SEC15b", "secret", "Phase 5: 'whole' removed", "then run the Phase 4 secrets command, whole, so that it greps that file", "then run the Phase 4 secrets command so that it greps that file")
m("SEC16", "secret", "Phase 5 secret bullet deleted", span("- Secret check: what the Phase 4 grep printed", "\n"), "")
m("SEC17", "secret", "no-shell 'not run' removed", ' Where there is no shell, give it inline and write "secret check: not run".', "")
m("SEC18", "secret", "grep-new-file-whole removed", "; grep a new file whole", "")
m("SEC19", "secret", "do-not-shorten sentence removed", " Copy it, do not retype it, and do not shorten the pattern; a shortened pattern is not this check.", "")
m("SEC20", "secret", "once-the-report-exists removed", "once the report file exists, run the command below whole", "run the command below whole")
# ---- surfaces / report / attribution
m("SF1", "surface", "paragraph deleted", span("**Where this runs.**", "\n\n"), "")
m("SF2", "surface", "chat/Cowork 'unverified' -> supported", "Claude chat and Claude Cowork: unverified for editing", "Claude chat and Claude Cowork: supported for editing")
m("SF3", "surface", "edit-nothing removed", " and edit nothing; a proposal needs no backup", "")
m("SF4", "surface", "backup-gate-applies-first removed", " If the surface does let you edit a file the user supplied, the Phase 3 backup gate applies first.", "")
m("RP1", "report", "LESSON bullet deleted", span("- Every `LESSON` line.", "\n"), "")
for i, cite in enumerate(["prompt.py:43", "diagnose.md:28", "schema.py:199", "prompt.py:24", "diagnose.md:23", "analyze_failures.py:75", "reflexion.py:114", "backup.py:38", "README.md:14"]):
    s = base.index(cite); st = base.rfind("(adapted from", 0, s); en = base.index("(MIT)", s) + 5
    en += 1 if base[en] == ")" else 0
    m(f"AT{i+1}", "attribution", "attribution line removed", base[st:en], "")
# ---- pattern (behaviour-tested)
def arms(e):
    res, depth, cur = [], 0, ""
    for ch in e:
        if ch in "([": depth += 1
        if ch in ")]": depth -= 1
        if ch == "|" and depth == 0: res.append(cur); cur = ""
        else: cur += ch
    return res + [cur]
A = arms(ERE)
for i, a in enumerate(A):
    new = ERE.replace(a + "|", "") if i < len(A) - 1 else ERE.replace("|" + a, "")
    m(f"ERE{i+1}", "pattern", "alternative removed", ERE, new)
def e(i, rule, o, n):
    assert o in ERE, (i, o); m(i, "pattern", rule, ERE, ERE.replace(o, n, 1))
e("ERE20", "sk 16->15", "\\bsk-[A-Za-z0-9_-]{16,}", "\\bsk-[A-Za-z0-9_-]{15,}")
e("ERE21", "sk 16->17", "\\bsk-[A-Za-z0-9_-]{16,}", "\\bsk-[A-Za-z0-9_-]{17,}")
e("ERE22", "ghp 20->19", "[pousr]_[A-Za-z0-9]{20,}", "[pousr]_[A-Za-z0-9]{19,}")
e("ERE23", "ghp 20->21", "[pousr]_[A-Za-z0-9]{20,}", "[pousr]_[A-Za-z0-9]{21,}")
e("ERE24", "github_pat 20->19", "github_pat_[A-Za-z0-9_]{20,}", "github_pat_[A-Za-z0-9_]{19,}")
e("ERE25", "github_pat 20->21", "github_pat_[A-Za-z0-9_]{20,}", "github_pat_[A-Za-z0-9_]{21,}")
e("ERE26", "AKIA 16->15", "AKIA[0-9A-Z]{16}", "AKIA[0-9A-Z]{15}")
e("ERE27", "AKIA 16->17", "AKIA[0-9A-Z]{16}", "AKIA[0-9A-Z]{17}")
e("ERE28", "sk_live 16->15", "(live|test)_[A-Za-z0-9]{16,}", "(live|test)_[A-Za-z0-9]{15,}")
e("ERE29", "sk_live 16->17", "(live|test)_[A-Za-z0-9]{16,}", "(live|test)_[A-Za-z0-9]{17,}")
e("ERE30", "sk_ drop test", "(live|test)", "(live)")
e("ERE31", "AIza 35->34", "AIza[A-Za-z0-9_-]{35}", "AIza[A-Za-z0-9_-]{34}")
e("ERE32", "AIza 35->36", "AIza[A-Za-z0-9_-]{35}", "AIza[A-Za-z0-9_-]{36}")
e("ERE33", "xox 10->9", "[A-Za-z0-9-]{10,}", "[A-Za-z0-9-]{9,}")
e("ERE34", "xox 10->11", "[A-Za-z0-9-]{10,}", "[A-Za-z0-9-]{11,}")
e("ERE35", "bearer 16->15", "bearer [A-Za-z0-9._~+/=-]{16,}", "bearer [A-Za-z0-9._~+/=-]{15,}")
e("ERE36", "bearer 16->17", "bearer [A-Za-z0-9._~+/=-]{16,}", "bearer [A-Za-z0-9._~+/=-]{17,}")
e("ERE37", "bearer class loses ~ (judge K03)", "bearer [A-Za-z0-9._~+/=-]", "bearer [A-Za-z0-9._+/=-]")
e("ERE38", "bearer class loses =", "bearer [A-Za-z0-9._~+/=-]", "bearer [A-Za-z0-9._~+/-]")
e("ERE39", "bearer class loses -", "bearer [A-Za-z0-9._~+/=-]", "bearer [A-Za-z0-9._~+/=]")
e("ERE40", "bearer class loses _", "bearer [A-Za-z0-9._~+/=-]", "bearer [A-Za-z0-9.~+/=-]")
e("ERE41", "basic 20->19", "basic [A-Za-z0-9+/=]{20,}", "basic [A-Za-z0-9+/=]{19,}")
e("ERE42", "basic 20->21", "basic [A-Za-z0-9+/=]{20,}", "basic [A-Za-z0-9+/=]{21,}")
e("ERE43", "jwt first segment 8->7", "eyJ[A-Za-z0-9_-]{8,}", "eyJ[A-Za-z0-9_-]{7,}")
e("ERE44", "jwt first segment 8->9", "eyJ[A-Za-z0-9_-]{8,}", "eyJ[A-Za-z0-9_-]{9,}")
e("ERE45", "jwt second segment 8->7", "\\.[A-Za-z0-9_-]{8,}\\.", "\\.[A-Za-z0-9_-]{7,}\\.")
e("ERE46", "jwt second segment 8->9", "\\.[A-Za-z0-9_-]{8,}\\.", "\\.[A-Za-z0-9_-]{9,}\\.")
e("ERE47", "jwt trailing dot dropped (judge K04)", "{8,}\\.[A-Za-z0-9_-]{8,}\\.|", "{8,}\\.[A-Za-z0-9_-]{8,}|")
e("ERE48", "jwt class loses - (judge K11)", "eyJ[A-Za-z0-9_-]{8,}", "eyJ[A-Za-z0-9_]{8,}")
e("ERE49", "kv value 12->11", "{12,}|://", "{11,}|://")
e("ERE50", "kv value 12->13", "{12,}|://", "{13,}|://")
e("ERE51", "kv post-gap {0,3}->{0,2} (judge K10)", "[:=][^A-Za-z0-9]{0,3}", "[:=][^A-Za-z0-9]{0,2}")
e("ERE52", "kv post-gap {0,3}->{0,4}", "[:=][^A-Za-z0-9]{0,3}", "[:=][^A-Za-z0-9]{0,4}")
e("ERE53", "kv pre-gap {0,3}->{0,2}", "[^A-Za-z0-9:=]{0,3}[:=]", "[^A-Za-z0-9:=]{0,2}[:=]")
e("ERE54", "kv pre-gap {0,3}->{0,4}", "[^A-Za-z0-9:=]{0,3}[:=]", "[^A-Za-z0-9:=]{0,4}[:=]")
for c in "/+_.@!#$%^&*-":
    pass
e("ERE55", "kv value class loses @", "_.@!#$%^&*-]{12,}", "_.!#$%^&*-]{12,}")
e("ERE56", "kv value class loses !", "_.@!#$%^&*-]{12,}", "_.@#$%^&*-]{12,}")
e("ERE57", "kv value class loses .", "[A-Za-z0-9/+_.@", "[A-Za-z0-9/+_@")
e("ERE58", "kv value class loses /", "[A-Za-z0-9/+_.@", "[A-Za-z0-9+_.@")
e("ERE59", "kv value class loses +", "[A-Za-z0-9/+_.@", "[A-Za-z0-9/_.@")
e("ERE60", "kv value class loses *", "%^&*-]{12,}", "%^&-]{12,}")
e("ERE61", "kv separator drops =", "[:=][^A-Za-z0-9]{0,3}", "[:][^A-Za-z0-9]{0,3}")
e("ERE62", "kv separator drops :", "[:=][^A-Za-z0-9]{0,3}", "[=][^A-Za-z0-9]{0,3}")
e("ERE63", "kv key drops password", "|token|password)", "|token)")
e("ERE64", "kv key drops secret", "|secret|token|", "|token|")
e("ERE65", "kv key drops api key variants", "api[_-]?key", "api_key")
e("ERE66", "kv key drops secret_key", "secret[_-]?(access[_-]?)?key|", "")
e("ERE67", "kv key drops access", "secret[_-]?(access[_-]?)?key", "secret[_-]?key")
for k, (o, n) in {"68": ("\\bsk-", "sk-"), "69": ("\\bgh[pousr]", "gh[pousr]"), "70": ("\\bxox", "xox"), "71": ("\\beyJ", "eyJ"), "72": ("\\bAIza", "AIza"), "73": ("\\bgithub_pat_", "github_pat_"), "74": ("\\bbasic ", "basic "), "75": ("\\bsk_(", "sk_(")}.items():
    e("ERE" + k, "word boundary removed", o, n)
e("ERE76", "gh letters drop r", "gh[pousr]_", "gh[pous]_")
e("ERE77", "xox letters drop s", "xox[abprs]-", "xox[abpr]-")
e("ERE78", "pem: drop PRIVATE", "PRIVATE KEY-----", "KEY-----")
e("ERE79", "url: empty user allowed", "://[^/ :@]+:[^/ @]+@", "://[^/ :@]*:[^/ @]+@")
e("ERE80", "url: needs no @", "://[^/ :@]+:[^/ @]+@", "://[^/ :@]+:[^/ @]+")
# ---- the judge's 30 prose and 15 pattern mutants (jmut.py, round 1), re-targeted where the text moved
def j(i, rule, o, n): m(i, "judge", rule, o, n)
j("J01", "never-copy list loses 'a memory note'", "a harness file or a memory note. Replace", "a harness file. Replace")
j("J02", "never-copy list loses 'the report'", "the change history, the report, a harness file", "the change history, a harness file")
j("J03", "redaction keeps the length", ", keeping no first or last characters, no length and no hash.", ", keeping no first or last characters and no length.")
j("J04", "Bearer threshold 40 (text)", "a `Bearer` or `Basic` credential", "a `Bearer` or `Basic` credential of 40 or more characters")
j("J05", "model deletes backups itself", "Do not delete a backup yourself; tell the user", "Delete the backup yourself once done; tell the user")
j("J06", "undo is rm", "To undo a change: `cp <file>.bak <file>`.", "To undo a change: `rm <file>.bak`.")
j("J07", "backup after last edit", "taken before that run's first edit to it", "taken after that run's last edit to it")
j("J08", "edit anyway", "edit nothing and say so. (adapted", "edit anyway and say so. (adapted")
j("J09", "quote the line in full", "Cite the file and line instead of quoting the line.", "Quote the line in full so the user can check it.")
j("J10", "grep -v", "   diff <backup> <file> | grep -niE \"$P\"", "   diff <backup> <file> | grep -viE \"$P\"")
j("J11", "report grep may print", "Any output is a leak: redact it and run the command again.", "Any output is fine.")
j("J12", "execution row says rule halted", "| execution | a step ran and a tool call failed, timed out or returned something unexpected |", "| execution | a rule halted the run on purpose |")
j("J13", "surfaces: chat does all", "**Where this runs.** Claude Code: all of it", "**Where this runs.** Claude chat: all of it")
j("J14", "surfaces: chat edits", "and edit nothing; a proposal needs no backup.", "and edit the files; a proposal needs no backup.")
j("J15", "evidence without line", "| evidence: <path>:<line> - <what in that line", "| evidence: <path> - <what in that line")
j("J16", "evidence after lesson", "6. **Open the evidence before you form a lesson.**", "6. **Open the evidence after you form a lesson.**")
j("J17", "fix apply for unclassified", "Use `fix: none` for an `unclassified` lesson.", "Use `fix: apply` for an `unclassified` lesson.")
j("J18", "one backup per run", "One backup per file per run, taken", "One backup per run, taken")
j("J19", "bak.2 overwritten", "use the first unused `<file>.bak.2`, `<file>.bak.3` and so on.", "use `<file>.bak.2` and overwrite it if present.")
j("J20", "shortened pattern fine", "Copy it, do not retype it, and do not shorten the pattern; a shortened pattern is not this check.", "A shortened pattern is fine.")
j("J21", "grep before the report", "then run the Phase 4 secrets command, whole, so that it greps that file, and give the user the same text.", "give the user the text, then run the Phase 4 secrets command, whole, so that it greps that file.")
j("J22", "new file gets .bak", "a file you create has no backup and is listed as new.", "a file you create gets its own `.bak` as well.")
j("J23", "attribution licence wrong", "(adapted from references/openharness/src/openharness/services/autodream/backup.py:38 (MIT))", "(adapted from references/openharness/src/openharness/services/autodream/backup.py:38 (Apache-2.0))")
j("J24", "diff -q says identical", "says the two now differ.", "says the two are identical.")
j("J25", "hit is false alarm", "Any output is a leak: redact it and run the command again.", "Any output is a false alarm: ignore it.")
j("J26", "when unsure keep", "When unsure, redact; the cost is a less specific lesson.", "When unsure, keep the value; the cost is a less specific lesson.")
j("J27", "cmp output ignored", "If the copy fails or `cmp` prints anything, edit nothing", "If the copy fails, edit nothing")
j("J29", "unclassified are applied", "`unclassified` ones are the feedback not applied", "`unclassified` ones are the feedback applied")
j("J30", "tie: first named by the user", "takes the earlier one in the order", "takes the first one named by the user in the order")
for i, o, n in [("K01", "\\bsk-[A-Za-z0-9_-]{16,}", "\\bsk-[A-Za-z0-9]{16,}"), ("K02", "AKIA[0-9A-Z]{16}", "AKIA[0-9]{16}"), ("K03", "bearer [A-Za-z0-9._~+/=-]{16,}", "bearer [A-Za-z0-9._+/=-]{16,}"),
                ("K04", "\\.[A-Za-z0-9_-]{8,}\\.|", "\\.[A-Za-z0-9_-]{8,}|"), ("K05", "(api[_-]?key|", "("), ("K06", "|\\bxox[abprs]-", "|xox[abprs]-"),
                ("K07", "[A-Za-z0-9/+_.@!#$%^&*-]{12,}", "[A-Za-z0-9/+_@!#$%^&*-]{12,}"), ("K08", "-----BEGIN [A-Z ]*PRIVATE KEY-----", "-----BEGIN [A-Z]*PRIVATE KEY-----"),
                ("K09", "[^/ :@]+:[^/ @]+@", "[^/ :@]+:[^/ @]+"), ("K10", "[:=][^A-Za-z0-9]{0,3}", "[:=][^A-Za-z0-9]{0,2}"), ("K11", "\\beyJ[A-Za-z0-9_-]{8,}", "\\beyJ[A-Za-z0-9_]{8,}"),
                ("K12", "\\bgh[pousr]_[A-Za-z0-9]{20,}", "\\bgh[pousr]_[A-Za-z0-9]{20,}|\\bghx_"), ("K13", "|://[^/ :@]+:[^/ @]+@", "|://[^/ :@]*:[^/ @]+@"),
                ("K14", "bearer [A-Za-z0-9", "bearer  [A-Za-z0-9"), ("PM4", "github_pat_[A-Za-z0-9_]{20,}", "github_pat_[A-Za-z0-9]{20,}"), ("PM16", "\\bsk-[A-Za-z0-9_-]{16,}", "\\bsk-[A-Za-z0-9-]{16,}"), ("K15", "\\bsk-", "\\bsk")]:
    assert o in ERE, (i, o); m(i, "judge", "judge pattern mutant", ERE, ERE.replace(o, n, 1))

sel = set(sys.argv[1:]); rows = []; survivors = []
for i, g, rule, old, new in out:
    if sel and i not in sel: continue
    assert base.count(old) == 1, (i, "old text count", base.count(old), old[:70])
    mutated = base.replace(old, new)
    assert mutated != base, (i, "no-op")
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "SKILL.md"; f.write_text(mutated, encoding="utf-8")
        tree = Path(td) / "tree/skills/finhub-harness-evolve"; tree.mkdir(parents=True); shutil.copy(f, tree / "SKILL.md")
        k = {"pins": subprocess.run([sys.executable, str(here / "pins.py"), str(f)], capture_output=True).returncode != 0,
             "greps": subprocess.run(["bash", str(here / "proof.sh"), str(Path(td) / "tree")], capture_output=True).returncode != 0,
             "behaviour": subprocess.run([sys.executable, str(here / "ere_tests.py"), str(f)], capture_output=True).returncode != 0}
    rows.append((i, g, rule, k))
    if not any(k.values()): survivors.append(i)
for i, g, rule, k in rows:
    print(f"{i:8s} {g:11s} {'BEHAVIOUR+presence' if k['behaviour'] and (k['pins'] or k['greps']) else 'BEHAVIOUR' if k['behaviour'] else 'presence only' if (k['pins'] or k['greps']) else 'SURVIVED':19s} {rule}")
beh = [r for r in rows if r[3]["behaviour"]]; pres = [r for r in rows if not r[3]["behaviour"] and any(r[3].values())]
print(f"mutants {len(rows)}, killed {len(rows) - len(survivors)}, survivors {len(survivors)}: {survivors}")
print(f"killed by a behaviour check (pattern tests): {len(beh)}; killed only by presence checks (pins, grep rows): {len(pres)}")
from collections import Counter
print("presence-only by group:", dict(Counter(r[1] for r in pres)), "| behaviour by group:", dict(Counter(r[1] for r in beh)))
sys.exit(1 if survivors else 0)
