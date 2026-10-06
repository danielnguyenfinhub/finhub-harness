"""C8 mutation runner (revision 2; C8_REV=1 selects the revision-1 source shape for the Z reproduction; C8_ONLY=Z runs one prefix). Usage: python 02_strategy-architect_C8_mutate.py <audited-tree> <scratch-dir> [python]

For every mutant: a fresh tar copy of src/ tests/ pyproject.toml of the audited tree, one exact-string
mutation (the old text must occur exactly once and the file must change: a no-op mutation is an error),
the mutated module path is checked to be the copy's, then a FRESH pytest process runs
tests/test_repeat_reminder.py and tests/test_loop.py. Killed = non-zero exit. Ordering mutants run
under PYTHONHASHSEED 0..39 and must be killed under every seed. Writes only under <scratch-dir>.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

R = "src/master_finhub/runtime/repeat_reminder.py"
L = "src/master_finhub/runtime/loop.py"


REV = os.environ.get("C8_REV", "2")
OBS = "self._repeat.observe(call.name, call.arguments)"
RUN = "redact_secrets(self._run_tool(call))[0]"
if REV == "1":  # revision 1: the notice is computed after the tool ran
    EXEC_OLD = "        result = " + RUN + "\n        return result + " + OBS + "\n"

    def ex(body: str) -> str:  # body uses {OBS}, {RUN}
        return body.format(OBS=OBS, RUN=RUN)
else:  # revision 2: the notice is computed before the tool runs
    EXEC_OLD = "        note = " + OBS + "\n        return " + RUN + " + note\n"

    def ex(body: str) -> str:
        return body.format(OBS=OBS, RUN=RUN)


@dataclass
class M:
    id: str
    what: str
    edits: list[tuple[str, str, str]]  # (file, old, new)
    seeds: bool = False  # ordering mutant: run under hash seeds 0..39
    equiv: str = ""  # non-empty: expected to survive; the reason it is equivalent
    killers: list[str] = field(default_factory=list)


def one(f: str, old: str, new: str) -> list[tuple[str, str, str]]:
    return [(f, old, new)]


MUTANTS: list[M] = [
    # --- thresholds: every member +-1, an extra member, 9+ behaviour -------------------------
    M("T1", "3 -> 2 (off by one down)", one(R, "(3, 5, 8)", "(2, 5, 8)")),
    M("T2", "3 -> 4 (off by one up)", one(R, "(3, 5, 8)", "(4, 5, 8)")),
    M("T3", "5 -> 4", one(R, "(3, 5, 8)", "(3, 4, 8)")),
    M("T4", "5 -> 6", one(R, "(3, 5, 8)", "(3, 6, 8)")),
    M("T5", "8 -> 7", one(R, "(3, 5, 8)", "(3, 5, 7)")),
    M("T6", "8 -> 9", one(R, "(3, 5, 8)", "(3, 5, 9)")),
    M("T7", "9 added (9+ must stay silent)", one(R, "(3, 5, 8)", "(3, 5, 8, 9)")),
    M("T8", "12 added", one(R, "(3, 5, 8)", "(3, 5, 8, 12)")),
    M("T9", "3 dropped", one(R, "(3, 5, 8)", "(5, 8)")),
    M("T10", "8 dropped", one(R, "(3, 5, 8)", "(3, 5)")),
    M("T11", "membership inverted", one(R, "if count not in REMIND_AT:", "if count in REMIND_AT:")),
    M("T12", "fires at every count >= 3 (< first)", one(R, "if count not in REMIND_AT:", "if count < REMIND_AT[0]:")),
    M("T13", "fires from 4 (<= first)", one(R, "if count not in REMIND_AT:", "if count <= REMIND_AT[0]:")),
    M("T14", "silent above 8 inverted (> last)", one(R, "if count not in REMIND_AT:", "if count > REMIND_AT[-1]:")),
    M("T15", "fires at every count >= 1", one(R, "if count not in REMIND_AT:", "if False:")),
    M("T16", "tier: gentle only at 3 -> not-equal", one(R, "count == REMIND_AT[0]", "count != REMIND_AT[0]")),
    M("T17", "tier: gentle at the second threshold", one(R, "count == REMIND_AT[0]", "count == REMIND_AT[1]")),
    M("T18", "tier: gentle at 3 and 5 (<= second)", one(R, "count == REMIND_AT[0]", "count <= REMIND_AT[1]")),
    M("T19", "tier: always firm", one(R, "(GENTLE if count == REMIND_AT[0] else FIRM.format(count=count))", "FIRM.format(count=count)")),
    M("T20", "tier: always gentle", one(R, "(GENTLE if count == REMIND_AT[0] else FIRM.format(count=count))", "GENTLE")),
    M("T21", "firm text shows count + 1", one(R, "FIRM.format(count=count)", "FIRM.format(count=count + 1)")),
    M("T22", "firm text shows a fixed 5", one(R, "FIRM.format(count=count)", "FIRM.format(count=5)")),
    M("T23", "separator \\n\\n -> \\n", one(R, 'return "\\n\\n" + (', 'return "\\n" + (')),
    M("T24", "no separator", one(R, 'return "\\n\\n" + (', 'return "" + (')),
    M("T25", "tier equivalent: gentle at < second", one(R, "count == REMIND_AT[0]", "count < REMIND_AT[1]"),
      equiv="count is already in {3,5,8}, so < 5 is the same set as == 3"),
    M("T26", "tier equivalent: gentle at <= first", one(R, "count == REMIND_AT[0]", "count <= REMIND_AT[0]"),
      equiv="count is already in {3,5,8}, so <= 3 is the same set as == 3"),
    # --- counter: increment, restart value, equality, storage -------------------------------
    M("C1", "increment by 2", one(R, "self._last[1] + 1", "self._last[1] + 2")),
    M("C2", "never increments", one(R, "self._last[1] + 1", "self._last[1]")),
    M("C3", "restart value 0 after a different call", one(R, "== key else 1", "== key else 0")),
    M("C4", "restart value 2 after a different call", one(R, "== key else 1", "== key else 2")),
    M("C5", "key equality inverted", one(R, "self._last[0] == key", "self._last[0] != key")),
    M("C6", "every call merged into one chain", one(R, "self._last is not None and self._last[0] == key", "self._last is not None")),
    M("C7", "identity compare instead of equality", one(R, "self._last[0] == key", "self._last[0] is key")),
    M("C8", "None check dropped (first call raises, fail-open)", one(R, "self._last is not None and self._last[0] == key", "self._last[0] == key")),
    M("C9", "chain never stored", one(R, "            self._last = (key, count)\n", "            pass\n")),
    M("C10", "chain stored with count 1", one(R, "self._last = (key, count)", "self._last = (key, 1)")),
    M("C11", "total count per call key (never reset by a different call)", [
        (R, "self._last: tuple[str, int] | None = None\n\n    def reset", "self._last: tuple[str, int] | None = None\n        self._seen: dict[str, int] = {}\n\n    def reset"),
        (R, "count = self._last[1] + 1 if self._last is not None and self._last[0] == key else 1\n",
         "count = self._seen.get(key, 0) + 1\n            self._seen[key] = count\n")]),
    M("C12", "reset() does nothing", one(R, "    def reset(self) -> None:\n        self._last = None", "    def reset(self) -> None:\n        pass")),
    # --- key: canonical form, name, args, output, cap, digest -------------------------------
    M("K1", "key order matters (sort_keys False)", one(R, "sort_keys=True", "sort_keys=False"), seeds=True),
    M("K2", "only the top level is key-sorted", one(R, "json.dumps([name, arguments], sort_keys=True,", "json.dumps([name, dict(sorted(arguments.items()) if isinstance(arguments, dict) else arguments)], sort_keys=False,"), seeds=True),
    M("K3", "set-based key (order free, nested values unhashable)", one(R, "text = json.dumps([name, arguments], sort_keys=True, separators=(\",\", \":\"))", "text = repr((name, frozenset(arguments.items())))"), seeds=True),
    M("K4", "name dropped from the key", one(R, "json.dumps([name, arguments]", "json.dumps([arguments]")),
    M("K5", "arguments dropped from the key", one(R, "json.dumps([name, arguments]", "json.dumps([name]")),
    M("K6", "default separators (cap counted on a longer text)", one(R, ', separators=(",", ":"))', ")")),
    M("K7", "cap: > becomes >=", one(R, "len(text) > MAX_KEY_CHARS", "len(text) >= MAX_KEY_CHARS")),
    M("K8", "cap: > MAX + 1", one(R, "len(text) > MAX_KEY_CHARS", "len(text) > MAX_KEY_CHARS + 1")),
    M("K9", "cap inverted", one(R, "len(text) > MAX_KEY_CHARS", "len(text) < MAX_KEY_CHARS")),
    M("K10", "cap removed", one(R, "len(text) > MAX_KEY_CHARS", "False")),
    M("K11", "cap constant changed", one(R, "MAX_KEY_CHARS: Final = 100_000", "MAX_KEY_CHARS: Final = 99_999")),
    M("K12", "unserialisable values stringified", one(R, 'sort_keys=True, separators=(",", ":"))', 'sort_keys=True, separators=(",", ":"), default=repr)')),
    M("K13", "key is the text, not a digest (memory)", one(R, 'return hashlib.sha256(text.encode("ascii")).hexdigest()', "return text")),
    M("K14", "key is hash(text) (same equality per process; the 64-char digest is pinned)", one(R, 'return hashlib.sha256(text.encode("ascii")).hexdigest()', "return str(hash(text))"), seeds=True),
    M("K15", "tool output goes into the key", one(L, EXEC_OLD, ex("        result = {RUN}\n        return result + self._repeat.observe(call.name, [call.arguments, result])\n"))),
    M("K16", "call id goes into the key", one(L, OBS, "self._repeat.observe(call.id, call.arguments)")),
    M("K17", "name dropped at the call site", one(L, OBS, 'self._repeat.observe("", call.arguments)')),
    M("K18", "arguments dropped at the call site", one(L, OBS, "self._repeat.observe(call.name, {})")),
    # --- fail-open: exception handling and the unkeyable path -------------------------------
    M("F1", "except narrowed to TypeError/ValueError", one(R, "except Exception:  # noqa", "except (TypeError, ValueError):  # noqa")),
    M("F2", "except widened to BaseException", one(R, "except Exception:  # noqa", "except BaseException:  # noqa")),
    M("F3", "except re-raises", one(R, "        except Exception:  # noqa: BLE001 - advisory only: odd arguments must not fail a call\n            self._last = None\n            return \"\"", "        except Exception:  # noqa: BLE001\n            raise")),
    M("F4", "except does not reset the chain", one(R, "        except Exception:  # noqa: BLE001 - advisory only: odd arguments must not fail a call\n            self._last = None\n", "        except Exception:  # noqa: BLE001\n            pass\n")),
    M("F5", "except returns None", one(R, "            self._last = None\n            return \"\"\n", "            self._last = None\n            return None  # type: ignore\n") ),
    M("F6", "except removed (try body only)", [
        (R, "        try:\n            key = _call_key", "        if True:\n            key = _call_key"),
        (R, "        except Exception:  # noqa: BLE001 - advisory only: odd arguments must not fail a call\n            self._last = None\n            return \"\"\n", "")]),
    M("F7", "no key: chain not reset", one(R, "            if key is None:\n                self._last = None\n                return \"\"", "            if key is None:\n                return \"\"")),
    M("F8", "no key branch removed (None keys chain up)", one(R, "            if key is None:\n                self._last = None\n                return \"\"\n", "")),
    M("F9", "no key: returns a reminder", one(R, "            if key is None:\n                self._last = None\n                return \"\"", "            if key is None:\n                self._last = None\n                return \"\\n\\n\" + GENTLE")),
    # --- loop call sites, reset points, order, pairing ---------------------------------------
    M("S1", "no reminder appended", one(L, EXEC_OLD, ex("        return {RUN}\n"))),
    M("S2", "reset missing in run()", one(L, "        self._repeat.reset()  # a new user prompt starts a new chain\n", "")),
    M("S3", "reset missing in resume()", one(L, "        self._repeat.reset()  # the chain is not in the snapshot, so it restarts here\n", "")),
    M("S4", "reset at the END of run() (a raised run leaks its count)", [
        (L, "        self._repeat.reset()  # a new user prompt starts a new chain\n", ""),
        (L, "        return self._drive(messages, 0, [])", "        done = self._drive(messages, 0, [])\n        self._repeat.reset()\n        return done")]),
    M("S5", "reset on every context fit (compaction)", one(L, "messages = self._context.fit(messages)", "messages = self._context.fit(messages)\n                self._repeat.reset()")),
    M("S6", "notice appended BEFORE the secret scan", one(L, EXEC_OLD, ex("        note = {OBS}\n        return redact_secrets(self._run_tool(call) + note)[0]\n"))),
    M("S7", "denials and errors not counted", one(L, EXEC_OLD, ex("        result = {RUN}\n        if result.startswith(\"Error:\"):\n            return result\n        return result + {OBS}\n"))),
    M("S8", "counted in _drive only (rerun path uncounted)", [
        (L, EXEC_OLD, ex("        return {RUN}\n")),
        (L, 'messages.append(Message("tool", self._execute(call), tool_call_id=call.id))', 'messages.append(Message("tool", self._execute(call) + ' + OBS + ", tool_call_id=call.id))")]),
    M("S9b", "uncertain result (report_unknown branch) counted too", one(L, "        if policy == \"report_unknown\":\n            return UNCERTAIN_RESULT", "        if policy == \"report_unknown\":\n            self._repeat.observe(call.name, call.arguments)\n            return UNCERTAIN_RESULT")),
    M("S9", "uncertain result (missing tool / guard branch) counted too", one(L, "        if tool is None or (self._guard is not None and self._guard(call) is not None):\n            return UNCERTAIN_RESULT", "        if tool is None or (self._guard is not None and self._guard(call) is not None):\n            self._repeat.observe(call.name, call.arguments)\n            return UNCERTAIN_RESULT")),
    M("S10", "state shared across loops (module level)", [
        (L, "        self._repeat = RepeatReminder()", "        self._repeat = _SHARED"),
        (L, "DEFAULT_MAX_STEPS = 20", "_SHARED = RepeatReminder()\nDEFAULT_MAX_STEPS = 20")]),
    M("S11", "the call is skipped from count 7 (a veto)", one(L, EXEC_OLD, ex("        note = {OBS}\n        skip = (self._repeat._last or (\"\", 0))[1] >= 6\n        return (\"skipped\" if skip else {RUN}) + note\n"))),
    M("S12", "result replaced by the notice (call result lost)", one(L, EXEC_OLD, ex("        note = {OBS}\n        result = {RUN}\n        return note.strip() or result\n"))),
    M("S13", "tool output copied into the reminder", one(L, EXEC_OLD, ex("        note = {OBS}\n        result = {RUN}\n        return result + note + (result[:12] if note else \"\")\n"))),
    M("S14", "arguments copied into the reminder", one(L, EXEC_OLD, ex("        note = {OBS}\n        result = {RUN}\n        return result + note + (repr(call.arguments) if note else \"\")\n"))),
    M("S15", "tool name copied into the reminder", one(L, EXEC_OLD, ex("        note = {OBS}\n        result = {RUN}\n        return result + note + (call.name if note else \"\")\n"))),
    M("S16", "reminder as its own user message (pair split)", [
        (L, EXEC_OLD, "        return redact_secrets(self._run_tool(call))[0]\n"),
        (L, 'messages.append(Message("tool", self._execute(call), tool_call_id=call.id))', 'messages.append(Message("tool", self._execute(call), tool_call_id=call.id))\n                note = ' + OBS + '\n                if note:\n                    messages.append(Message("user", note))')]),
    M("S17", "count AFTER the run (the rev 1 order; a tool that edits its arguments merges calls)", one(L, EXEC_OLD, ex("        result = {RUN}\n        return result + {OBS}\n"))),
    M("S18", "resume() of a completed snapshot does not reset (equivalent)", one(L, "        self._repeat.reset()  # the chain is not in the snapshot, so it restarts here\n        self._save(snapshot.step, list(snapshot.messages))\n        if snapshot.status == \"completed\":\n            return snapshot.messages[-1].content\n", "        self._save(snapshot.step, list(snapshot.messages))\n        if snapshot.status == \"completed\":\n            return snapshot.messages[-1].content\n        self._repeat.reset()\n"),
      equiv="a completed snapshot runs no call, and the next run() or resume() resets first"),
    M("S19", "observer built per call (never counts)", one(L, EXEC_OLD, ex("        note = RepeatReminder().observe(call.name, call.arguments)\n        return {RUN} + note\n"))),

    # --- revision 2: the judge's round-1 classes (B1-B5), plus a few of my own -------------------
    M("Z1", "digest cut to one hex char", one(R, ".hexdigest()", ".hexdigest()[:1]")),
    M("Z2", "ensure_ascii=False (non-ASCII arguments become untracked)", one(R, 'separators=(",", ":"))', 'separators=(",", ":"), ensure_ascii=False)')),
    M("Z3", "allow_nan=False (NaN arguments untracked)", one(R, 'separators=(",", ":"))', 'separators=(",", ":"), allow_nan=False)')),
    M("Z4", "except narrowed to TypeError/ValueError/RuntimeError", one(R, "except Exception:  # noqa", "except (TypeError, ValueError, RuntimeError):  # noqa")),
    M("Z5", "except narrowed to six named classes (no MemoryError)", one(R, "except Exception:  # noqa", "except (TypeError, ValueError, RuntimeError, RecursionError, OverflowError, KeyError):  # noqa")),
    M("Z6", "name lower-cased", one(R, "json.dumps([name, arguments]", "json.dumps([name.lower(), arguments]")),
    M("Z7", "name stripped", one(R, "json.dumps([name, arguments]", "json.dumps([name.strip(), arguments]")),
    M("Z8", "key text lower-cased", one(R, "    if len(text) > MAX_KEY_CHARS:", "    text = text.lower()\n    if len(text) > MAX_KEY_CHARS:")),
    M("Z9", "spaces removed from the key text", one(R, "    if len(text) > MAX_KEY_CHARS:", "    text = text.replace(\" \", \"\")\n    if len(text) > MAX_KEY_CHARS:")),
    M("Z11", "run length stored capped at 9 (equivalent: 9 and above are silent anyway)", one(R, "self._last = (key, count)", "self._last = (key, min(count, 9))"),
      equiv="a stored count of 9 still gives 9, 10... and none of them is in (3, 5, 8)"),
    M("Z14", "an empty tool result gets no reminder", one(L, EXEC_OLD, ex("        note = {OBS}\n        r = {RUN}\n        return r + (note if r else \"\")\n"))),
    M("Z15", "a result over 60,000 characters gets no reminder", one(L, EXEC_OLD, ex("        note = {OBS}\n        r = {RUN}\n        return r + (note if len(r) <= 60000 else \"\")\n"))),
    M("Z17", "resume() resets only when calls are pending (the team.py path)", one(L, "        self._repeat.reset()  # the chain is not in the snapshot, so it restarts here\n", "        if snapshot.pending_calls:\n            self._repeat.reset()\n")),
    M("Z21", "chain cleared at the start of every multi-call turn", one(L, "            for call in pending:\n", "            if len(pending) > 1:\n                self._repeat.reset()\n            for call in pending:\n")),
    M("Z35", "null merged with the empty string", one(R, "    if len(text) > MAX_KEY_CHARS:", "    text = text.replace(\"null\", '\"\"')\n    if len(text) > MAX_KEY_CHARS:")),
    M("Z36", "name and arguments swapped in the key (equivalent: same equality)", one(R, "json.dumps([name, arguments]", "json.dumps([arguments, name]"),
      equiv="the pair is still unique per call; only the digest changes"),
]


def pycopy(src_tree: Path, dest: Path) -> None:
    tar = dest.parent / (dest.name + ".tar")
    with tarfile.open(tar, "w") as t:
        for item in ("src", "tests", "pyproject.toml"):
            t.add(src_tree / item, arcname=item, filter=lambda ti: None if "__pycache__" in ti.name else ti)
    with tarfile.open(tar) as t:
        t.extractall(dest, filter="data")
    tar.unlink()


def run_pytest(copy: Path, py: str, seed: str | None) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUNBUFFERED", "PYTHONPATH", "PYTHONHASHSEED")}
    env["PYTHONPATH"] = str(copy / "src")
    if seed is not None:
        env["PYTHONHASHSEED"] = seed
    p = subprocess.run([py, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header",
                        "tests/test_repeat_reminder.py", "tests/test_loop.py"],
                       cwd=copy, env=env, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def check_path(copy: Path, py: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(copy / "src")}
    out = subprocess.run([py, "-B", "-c", "import master_finhub.runtime.loop as m; print(m.__file__)"],
                         cwd=copy, env=env, capture_output=True, text=True, check=True).stdout.strip()
    assert out.startswith(str(copy)), f"imports {out}, not the copy"


def main() -> int:
    tree, scratch = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    py = sys.argv[3] if len(sys.argv) > 3 else sys.executable
    scratch.mkdir(parents=True, exist_ok=True)
    only = os.environ.get("C8_ONLY")
    if only:
        MUTANTS[:] = [m for m in MUTANTS if m.id.startswith(only)]
    ids = [m.id for m in MUTANTS]
    assert len(ids) == len(set(ids))
    base = Path(tempfile.mkdtemp(prefix="c8ctl_", dir=scratch))
    pycopy(tree, base / "t")
    check_path(base / "t", py)
    rc, out = run_pytest(base / "t", py, None)
    print(f"CONTROL (unmutated copy): rc={rc} {out.strip().splitlines()[-1]}")
    if rc != 0:
        return 2
    killed = survived_eq = bad = 0
    rows = []
    for m in MUTANTS:
        d = Path(tempfile.mkdtemp(prefix=f"c8_{m.id}_", dir=scratch))
        pycopy(tree, d / "t")
        copy = d / "t"
        delta = 0
        for f, old, new in m.edits:
            path = copy / f
            text = path.read_text()
            assert text.count(old) == 1, f"{m.id}: old text occurs {text.count(old)} times in {f}"
            mutated = text.replace(old, new)
            assert mutated != text, f"{m.id}: no-op mutation"
            delta += sum(1 for ln in difflib.unified_diff(text.splitlines(), mutated.splitlines(), lineterm="")
                         if ln[:1] in "+-" and ln[:3] not in ("+++", "---"))
            path.write_text(mutated)
            assert path.read_text() != text
        check_path(copy, py)
        seeds = [str(s) for s in range(40)] if m.seeds else [None]
        results = [run_pytest(copy, py, s) for s in seeds]
        dead = [rc != 0 for rc, _ in results]
        failed = sorted({re.sub(r".*::", "", ln.split(" ")[1]).split("[")[0] for _, o in results for ln in o.splitlines() if ln.startswith("FAILED ")})
        status = "KILLED" if all(dead) else ("SURVIVED" if not any(dead) else "FLAKY-PARTIAL")
        if status == "KILLED":
            killed += 1
        elif m.equiv and status == "SURVIVED":
            survived_eq += 1
        else:
            bad += 1
        tag = f"x{len(seeds)} seeds" if m.seeds else "1 run"
        eq = f" [equivalent: {m.equiv}]" if m.equiv and status == "SURVIVED" else ""
        print(f"{m.id:4} {status:9} diff-lines={delta:2} {tag:11} {m.what} -> {', '.join(failed[:3])}{'...' if len(failed) > 3 else ''}{eq}", flush=True)
        rows.append((m.id, status))
    n = len(MUTANTS)
    print(f"TOTAL {n}: killed {killed}, survived-equivalent {survived_eq}, unexpected survivors/partial {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
