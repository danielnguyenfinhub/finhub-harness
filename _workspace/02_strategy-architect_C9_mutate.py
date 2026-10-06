"""C9 mutation runner. Usage: python 02_strategy-architect_C9_mutate.py <audited-tree> <scratch-dir> [python]

For every mutant: a fresh tar copy of the whole audited tree (src/, tests/, skills/, .claude/, scripts/,
pyproject.toml and .gitignore; never .git or __pycache__), one or more exact-string edits (each old text
must occur exactly the stated number of times and the file must change: a no-op mutation is an error),
the mutated module path is checked to be the copy's, then a FRESH `python -B -m pytest -x` process runs
tests/test_gates.py. Killed = non-zero exit (a timeout counts as killed and is flagged). Ordering mutants
run under PYTHONHASHSEED 0..39 and must be killed under every seed. A mutant killed ONLY by timing-
sensitive tests is re-run alone, serially, and counts as killed only if it fails again. Env:
C9_DRY=1 applies every edit and runs nothing; C9_ONLY=<id prefix>; C9_JOBS=<parallel workers>.
Writes only under <scratch-dir>.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

G = "src/master_finhub/evals/gates.py"
S = "src/master_finhub/sandbox/stream.py"
TESTS = ["tests/test_gates.py"]
TIMING = {
    "test_total_budget_caps_the_running_gate_and_skips_the_rest",
    "test_timeout_kills_the_whole_process_group",
    "test_durations_are_small_non_negative_numbers",
    "test_proof_timeout_is_timeout_never_pass",
    "test_huge_output_is_bounded",
    "test_pathological_commands_are_fast",
    "test_oversized_commands_are_refused_without_parsing",
    "test_file_size_cap_applies_before_parsing",
    "test_a_daemonised_grandchild_holding_the_pipe_is_a_timeout_not_a_pass",
    "test_timeout_keeps_the_output_so_far",
    "test_per_gate_timeout_is_the_smaller_of_gate_and_remaining",
}


@dataclass
class M:
    id: str
    what: str
    edits: list[tuple]  # (file, old, new) or (file, old, new, expected_count)
    seeds: bool = False
    equiv: str = ""
    killers: list[str] = field(default_factory=list)


def one(f: str, old: str, new: str, n: int = 1) -> list[tuple]:
    return [(f, old, new, n)]


def const(i: str, what: str, old: str, new: str, f: str = G) -> M:
    return M(i, what, one(f, old, new))


MUTANTS: list[M] = []
add = MUTANTS.append

# --- constants and bounds ---------------------------------------------------------------------
for i, (what, old, new) in enumerate(
    [
        ("MAX_GATES 51", "MAX_GATES: Final = 50", "MAX_GATES: Final = 51"),
        ("MAX_GATES 49", "MAX_GATES: Final = 50", "MAX_GATES: Final = 49"),
        ("MAX_FILE_BYTES -1", "MAX_FILE_BYTES: Final = 262_144", "MAX_FILE_BYTES: Final = 262_143"),
        ("MAX_FILE_BYTES +1", "MAX_FILE_BYTES: Final = 262_144", "MAX_FILE_BYTES: Final = 262_145"),
        ("MAX_TEXT_CHARS 4095", "MAX_TEXT_CHARS: Final = 4096", "MAX_TEXT_CHARS: Final = 4095"),
        ("MAX_TEXT_CHARS 4097", "MAX_TEXT_CHARS: Final = 4096", "MAX_TEXT_CHARS: Final = 4097"),
        ("MAX_ARGV_ITEMS 255", "MAX_ARGV_ITEMS: Final = 256", "MAX_ARGV_ITEMS: Final = 255"),
        ("MAX_ARGV_ITEMS 257", "MAX_ARGV_ITEMS: Final = 256", "MAX_ARGV_ITEMS: Final = 257"),
        ("DEFAULT_TIMEOUT_S 299", "DEFAULT_TIMEOUT_S: Final = 300.0", "DEFAULT_TIMEOUT_S: Final = 299.0"),
        ("MAX_TIMEOUT_S 1799", "MAX_TIMEOUT_S: Final = 1800.0", "MAX_TIMEOUT_S: Final = 1799.0"),
        ("MAX_TIMEOUT_S 1801", "MAX_TIMEOUT_S: Final = 1800.0", "MAX_TIMEOUT_S: Final = 1801.0"),
        ("MAX_TOTAL_S 3601", "MAX_TOTAL_S: Final = 3600.0", "MAX_TOTAL_S: Final = 3601.0"),
        ("TAIL_CHARS 3999", "TAIL_CHARS: Final = 4000", "TAIL_CHARS: Final = 3999"),
        ("TAIL_CHARS 4001", "TAIL_CHARS: Final = 4000", "TAIL_CHARS: Final = 4001"),
        ("SHELL_PATH bash", 'SHELL_PATH: Final = "/bin/sh"', 'SHELL_PATH: Final = "/bin/bash"'),
        ("SCHEMA_VERSION 2", "SCHEMA_VERSION: Final = 1", "SCHEMA_VERSION: Final = 2"),
    ],
    1,
):
    add(const(f"K{i:02d}", what, old, new))

TOKENS = [";", "&", "|", "`", "$", "<", ">", "\\n", "\\r"]
for i, tok in enumerate(TOKENS):
    rest = "".join(t for t in TOKENS if t != tok)
    add(
        const(
            f"X{i + 1:02d}",
            f"metacharacter {tok!r} dropped from the set",
            'frozenset(";&|`$<>\\n\\r")',
            f'frozenset("{rest}")',
        )
    )
for i, extra in enumerate(["(", ")", "{", "*", "~", "#", "!", "\\t", "'", "?", "[", "="], 10):
    add(
        const(
            f"X{i:02d}",
            f"false positive: {extra!r} added to the metacharacter set",
            'frozenset(";&|`$<>\\n\\r")',
            f'frozenset(";&|`$<>\\n\\r{extra}")',
        )
    )
add(const("X30", "root keys: extra accepted", 'frozenset({"schema_version", "gates"})', 'frozenset({"schema_version", "gates", "extra"})'))
add(const("X31", "gate keys: env accepted", '"shell", "timeout_s", "cwd"})', '"shell", "timeout_s", "cwd", "env"})'))
add(const("X32", "gate keys: cwd dropped", '"shell", "timeout_s", "cwd"})', '"shell", "timeout_s"})'))

# --- the file: strict schema ------------------------------------------------------------------
L = [
    ("L01", "isfile check removed", "    if not os.path.isfile(path):", "    if False:"),
    ("L02", "unbounded read", "fh.read(MAX_FILE_BYTES + 1)", "fh.read()"),
    ("L03", "read one byte short (size cap never trips)", "fh.read(MAX_FILE_BYTES + 1)", "fh.read(MAX_FILE_BYTES)"),
    ("L04", "size cap: > becomes >=", "if len(raw) > MAX_FILE_BYTES:", "if len(raw) >= MAX_FILE_BYTES:"),
    ("L05", "size cap removed", "if len(raw) > MAX_FILE_BYTES:", "if False:"),
    ("L06", "decode errors replaced", 'raw.decode("utf-8")', 'raw.decode("utf-8", errors="replace")'),
    ("L07", "BOM tolerated", 'raw.decode("utf-8")', 'raw.decode("utf-8-sig")'),
    ("L08", "latin-1 decode", 'raw.decode("utf-8")', 'raw.decode("latin-1")'),
    ("L09", "duplicate keys allowed", ", object_pairs_hook=_unique_keys)", ")"),
    ("L10", "RecursionError not caught", "except (ValueError, RecursionError):", "except ValueError:"),
    ("L11", "ValueError not caught", "except (ValueError, RecursionError):", "except RecursionError:"),
    ("L12", "unknown root keys allowed", "if not isinstance(data, dict) or not set(data) <= ROOT_KEYS:", "if not isinstance(data, dict):"),
    ("L13", "root type check removed", "if not isinstance(data, dict) or not set(data) <= ROOT_KEYS:", "if not set(data) <= ROOT_KEYS:"),
    ("L14", "version: bool and 1.0 pass", "if type(version) is not int or version != SCHEMA_VERSION:", "if version != SCHEMA_VERSION:"),
    ("L15", "version: any int passes", "if type(version) is not int or version != SCHEMA_VERSION:", "if type(version) is not int:"),
    ("L16", "version: 1.0 passes", "if type(version) is not int or version != SCHEMA_VERSION:", "if isinstance(version, bool) or version != SCHEMA_VERSION:"),
    ("L17", "version check removed", "if type(version) is not int or version != SCHEMA_VERSION:", "if False:"),
    ("L18", "empty gate list allowed", "if not isinstance(rows, list) or not rows:", "if not isinstance(rows, list):"),
    ("L19", "gates list type not checked", "if not isinstance(rows, list) or not rows:", "if not rows:"),
    ("L20", "gate count: > becomes >=", "if len(rows) > MAX_GATES:", "if len(rows) >= MAX_GATES:"),
    ("L21", "gate count cap removed", "if len(rows) > MAX_GATES:", "if False:"),
    ("L22", "duplicate ids: != becomes >", "if len({g.id for g in gates}) != len(gates):", "if len({g.id for g in gates}) > len(gates):"),
    ("L23", "duplicate id check removed", "if len({g.id for g in gates}) != len(gates):", "if False:"),
    ("L24", "duplicate ids: != becomes <", "if len({g.id for g in gates}) != len(gates):", "if len({g.id for g in gates}) < len(gates):"),
    ("L25", "gate numbering starts at 0", "enumerate(rows, 1)", "enumerate(rows, 0)"),
    ("L26", "last gate dropped at load", "    gates = tuple(_parse_gate(i, row) for i, row in enumerate(rows, 1))\n", "    gates = tuple(_parse_gate(i, row) for i, row in enumerate(rows, 1))[:-1]\n"),
    ("L27", "first gate dropped at load", "    gates = tuple(_parse_gate(i, row) for i, row in enumerate(rows, 1))\n", "    gates = tuple(_parse_gate(i, row) for i, row in enumerate(rows, 1))[1:]\n"),
    ("L28", "gates beyond the cap truncated, not refused", "    if len(rows) > MAX_GATES:\n        raise _bad(f\"more than {MAX_GATES} gates\")\n", "    rows = rows[:MAX_GATES]\n"),
    ("P01", "gate object check removed", "    if not isinstance(entry, dict):", "    if False:"),
    ("P02", "unknown gate keys allowed", "    if not set(entry) <= GATE_KEYS:", "    if False:"),
    ("P03", "id check removed", '    if not _valid_id(entry.get("id")):', "    if False:"),
    ("P04", "empty id allowed", "0 < len(value) <= 64", "len(value) <= 64"),
    ("P05", "id length 65 allowed", "0 < len(value) <= 64", "0 < len(value) <= 65"),
    ("P06", "id length 64 refused", "0 < len(value) <= 64", "0 < len(value) < 64"),
    ("P07", "non-ASCII ids allowed", "        and value.isascii()\n", ""),
    ("P08", "leading punctuation in ids allowed", "        and value[0].isalnum()\n", ""),
    ("P09", "space allowed in ids", 'c in "._-" for c', 'c in "._- " for c'),
    ("P10", "slash allowed in ids", 'c in "._-" for c', 'c in "._-/" for c'),
    ("P11", "dot not allowed in ids", 'c in "._-" for c', 'c in "_-" for c'),
    ("P12", "dash not allowed in ids", 'c in "._-" for c', 'c in "._" for c'),
    ("P13", "underscore not allowed in ids", 'c in "._-" for c', 'c in ".-" for c'),
    ("P14", "id type not checked", "        isinstance(value, str)\n        and 0 <", "        0 <"),
    ("P15", "command and argv together allowed", "if (command is None) == (argv is None):", "if (command is None) and (argv is None):"),
    ("P16", "command or argv alone refused", "if (command is None) == (argv is None):", "if (command is None) or (argv is None):"),
    ("P17", "command type not checked", "    if command is not None and not isinstance(command, str):", "    if False:"),
    ("P18", "argv type not checked", "    if argv is not None and not (isinstance(argv, list) and all(isinstance(a, str) for a in argv)):", "    if False:"),
    ("P19", "argv list type not checked", "not (isinstance(argv, list) and all(", "not (all("),
    ("P20", "argv item types not checked", "all(isinstance(a, str) for a in argv)):\n        raise _bad(f\"gate {n}: argv", "True):\n        raise _bad(f\"gate {n}: argv"),
    ("P21", "shell flag type not checked", "    if not isinstance(shell, bool):", "    if False:"),
    ("P22", "shell flag coerced with bool() (the reference's bug)", '    shell = entry.get("shell", False)\n    if not isinstance(shell, bool):', '    shell = bool(entry.get("shell", False))\n    if False:'),
    ("P23", "shell with argv allowed", "    if shell and command is None:", "    if False:"),
    ("P24", "timeout default None", 'if "timeout_s" in entry else DEFAULT_TIMEOUT_S', 'if "timeout_s" in entry else None'),
    ("P25", "bool timeout allowed", "    if isinstance(value, bool) or not isinstance(value, (int, float)):", "    if not isinstance(value, (int, float)):"),
    ("P26", "string timeout allowed", "    if isinstance(value, bool) or not isinstance(value, (int, float)):", "    if isinstance(value, bool):"),
    ("P27", "OverflowError not caught", "    except OverflowError:", "    except KeyError:"),
    ("P28", "timeout 0 allowed", "0 < seconds <= MAX_TIMEOUT_S", "0 <= seconds <= MAX_TIMEOUT_S"),
    ("P29", "timeout upper bound exclusive", "0 < seconds <= MAX_TIMEOUT_S", "0 < seconds < MAX_TIMEOUT_S"),
    ("P30", "timeout upper bound removed", "0 < seconds <= MAX_TIMEOUT_S", "0 < seconds"),
    ("P31", "timeout lower bound removed", "0 < seconds <= MAX_TIMEOUT_S", "seconds <= MAX_TIMEOUT_S"),
    ("P32", "default cwd empty", 'entry.get("cwd", ".")', 'entry.get("cwd", "")'),
    ("P33", "cwd type not checked", "    if not isinstance(cwd, str):", "    if False:"),
    ("P34", "argv kept as a list", "None if argv is None else tuple(argv)", "argv"),
]
for i, what, old, new in L:
    add(M(i, what, one(G, old, new)))
    if i == "L24":
        MUTANTS[-1].equiv = "a set is never larger than its list, so `!=` and `<` are the same test"
add(M("P35", "timeout default is the max", one(G, "else DEFAULT_TIMEOUT_S", "else MAX_TIMEOUT_S")))
add(M("P36", "NaN timeout accepted (negated comparison)", one(G, "0 < seconds <= MAX_TIMEOUT_S else None", "not (seconds <= 0 or seconds > MAX_TIMEOUT_S) else None")))

# --- the policy: string -> argv, argv checks, plan --------------------------------------------
A = [
    ("A01", "command string not stripped", "    text = raw.strip()\n", "    text = raw\n"),
    ("A02", "command length: > becomes >=", "    if len(text) > MAX_TEXT_CHARS:", "    if len(text) >= MAX_TEXT_CHARS:"),
    ("A03", "command length cap removed", "    if len(text) > MAX_TEXT_CHARS:", "    if False:"),
    ("A04", "metacharacters: first word only", "if any(ch in SHELL_METACHARS for ch in text):", "if any(ch in SHELL_METACHARS for ch in (text.split() or [\"\"])[0]):"),
    ("A05", "metacharacter scan removed", "    if any(ch in SHELL_METACHARS for ch in text):", "    if False:"),
    ("A06", "metacharacter scan inverted", "    if any(ch in SHELL_METACHARS for ch in text):", "    if not any(ch in SHELL_METACHARS for ch in text):"),
    ("A07", "split on whitespace only", "return tuple(shlex.split(text))", "return tuple(text.split())"),
    ("A08", "shlex comments on", "return tuple(shlex.split(text))", "return tuple(shlex.split(text, comments=True))"),
    ("A09", "shlex non-POSIX", "return tuple(shlex.split(text))", "return tuple(shlex.split(text, posix=False))"),
    ("A10", "tokenize error not handled", "    except ValueError:\n        return \"could not tokenize", "    except KeyError:\n        return \"could not tokenize"),
    ("R01", "empty argv allowed", "    if not argv:\n        return \"empty command\"", "    if False:\n        return \"empty command\""),
    ("R02", "argv count: > becomes >=", "if len(argv) > MAX_ARGV_ITEMS or", "if len(argv) >= MAX_ARGV_ITEMS or"),
    ("R03", "argv item length: > becomes >=", "any(len(a) > MAX_TEXT_CHARS for a in argv)", "any(len(a) >= MAX_TEXT_CHARS for a in argv)"),
    ("R04", "argv size caps removed", "    if len(argv) > MAX_ARGV_ITEMS or any(len(a) > MAX_TEXT_CHARS for a in argv):", "    if False:"),
    ("R05", "NUL check removed", '    if any("\\x00" in a for a in argv):', "    if False:"),
    ("R06", "encode check removed", "            a.encode(\"utf-8\")\n", "            pass\n"),
    ("R07", "encode check lets lone surrogates through", 'a.encode("utf-8")', 'a.encode("utf-8", "surrogateescape")'),
    ("R08", "empty executable allowed", "    if not argv[0]:", "    if False:"),
    ("R09", "leading dash allowed", '    if argv[0].startswith("-"):', "    if False:"),
    ("R10", "'=' in the executable allowed", '    if "=" in argv[0]:', "    if False:"),
    ("R11", "'=' checked on the last word", '    if "=" in argv[0]:', '    if "=" in argv[-1]:'),
    ("R12", "leading dash checked on every word", '    if argv[0].startswith("-"):', '    if any(a.startswith("-") for a in argv):'),
    ("R13", "'=' checked on every word", '    if "=" in argv[0]:', '    if any("=" in a for a in argv):'),
    ("Q01", "shell flag ignored", "        if gate.shell:", "        if False:"),
    ("Q02", "blank shell command allowed", "            if not raw.strip():", "            if not raw:"),
    ("Q03", "shell length: > becomes >=", "            if len(raw) > MAX_TEXT_CHARS:", "            if len(raw) >= MAX_TEXT_CHARS:"),
    ("Q04", "shell length cap removed", "            if len(raw) > MAX_TEXT_CHARS:", "            if False:"),
    ("Q05", "shell runs without the caller flag", "            if not allow_shell:", "            if False:"),
    ("Q06", "shell caller flag inverted", "            if not allow_shell:", "            if allow_shell:"),
    ("Q07", "non-POSIX check inverted", '            if os.name != "posix":', '            if os.name == "posix":'),
    ("Q08", "non-POSIX check removed", '            if os.name != "posix":', "            if False:"),
    ("Q09", "shell argv: -lc", '(SHELL_PATH, "-c", raw)', '(SHELL_PATH, "-lc", raw)'),
    ("Q10", "shell argv: bare sh", '(SHELL_PATH, "-c", raw)', '("sh", "-c", raw)'),
    ("Q11", "guard sees the sh -c line", "            line = raw\n", "            line = shlex.join(argv)\n"),
    ("Q12", "argv-form gates ignored", "parsed = _argv_from_string(gate.command) if gate.command is not None else gate.argv", 'parsed = _argv_from_string(gate.command or "")'),
    ("Q13", "refusal text not returned", "            if isinstance(parsed, str):\n                return parsed\n", "            if False:\n                return parsed\n"),
    ("Q14", "empty argv replaced by `true` (a silent pass)", "            argv = parsed or ()\n", '            argv = parsed or ("true",)\n'),
    ("Q15", "guard sees a space-joined line", "            line = shlex.join(argv)\n", '            line = " ".join(argv)\n'),
    ("Q16", "argv checks skipped", "        refusal = _argv_refusal(argv)\n", "        refusal = None\n"),
    ("Q17", "cwd checked in write mode", "ws.check_read(gate.cwd)", "ws.check_write(gate.cwd)"),
    ("Q18", "cwd not fenced (Path only)", "ws.check_read(gate.cwd)", "Path(gate.cwd)"),
    ("Q19", "cwd joined to the root without containment", "ws.check_read(gate.cwd)", "(ws.root / gate.cwd)"),
    ("Q20", "cwd denial not handled", "        except SandboxDenied as exc:", "        except KeyError as exc:"),
    ("Q21", "cwd folder check removed", "        if not cwd.is_dir():", "        if False:"),
    ("Q22", "cwd folder check: exists", "        if not cwd.is_dir():", "        if not cwd.exists():"),
    ("R14", "argv refusal inverted", "        if refusal is not None:\n            return refusal", "        if refusal is None:\n            return refusal"),
    ("Q22b", "cwd folder check inverted", "        if not cwd.is_dir():", "        if cwd.is_dir():"),
    ("Q25b", "guard denial inverted", "        if denial is not None:\n            return denial", "        if denial is None:\n            return denial"),
    ("Q31", "metacharacter refusal echoes the command", 'return "shell metacharacters; use argv, or declare shell: true and pass --allow-shell"', 'return f"shell metacharacters in {text}; use argv, or declare shell: true and pass --allow-shell"'),
    ("Q32", "tokenize refusal echoes the command", 'return "could not tokenize the command (unbalanced quote or trailing backslash)"', 'return f"could not tokenize {text}"'),
    ("Q33", "leading-dash refusal echoes the word", 'return "the executable starts with \'-\'"', 'return f"the executable {argv[0]} starts with \'-\'"'),
    ("Q34", "cwd refusal echoes the cwd", 'return f"cwd refused ({exc.reason})"', 'return f"cwd refused ({gate.cwd})"'),
    ("Q35", "cwd folder refusal echoes the cwd", 'return "cwd is not a folder"', 'return f"cwd is not a folder: {gate.cwd}"'),
    ("Q23", "guard not called", '        denial = guard_tool_call(ToolCall("gate", "gate", {"command": line, "cwd": str(cwd)}))', "        denial = None"),
    ("Q24", "guard not given the cwd (sensitive-path rule on cwd lost)", '{"command": line, "cwd": str(cwd)}', '{"command": line}'),
    ("Q24b", "guard given the wrong command key", '{"command": line, "cwd": str(cwd)}', '{"note": line, "cwd": str(cwd)}'),
    ("Q24c", "guard given the gate cwd text, not the resolved path", '{"command": line, "cwd": str(cwd)}', '{"command": line, "cwd": gate.cwd}'),
    ("Q24d", "guard fed the raw string for argv gates", '{"command": line, "cwd": str(cwd)}', '{"command": " ".join(argv), "cwd": str(cwd)}'),
    ("Q25", "guard denial replaced by a fixed word", "        if denial is not None:\n            return denial", "        if denial is not None:\n            return \"denied\""),
    ("Q26", "plan uses the root, not the gate cwd", "        return Plan(argv, cwd)", "        return Plan(argv, ws.root)"),
    ("Q27", "plan drops the first word", "        return Plan(argv, cwd)", "        return Plan(argv[1:], cwd)"),
    ("Q28", "unexpected policy error not caught", "    except Exception:  # noqa: BLE001 - fail closed: an unexpected error is a refusal", "    except KeyError:  # noqa: BLE001"),
    ("Q29", "unexpected policy error returns None", '        return "policy check failed"', "        return None  # type: ignore[return-value]"),
    ("Q30", "unexpected policy error is a pass-through plan", '        return "policy check failed"', "        return Plan(('true',), ws.root)"),
]
for i, what, old, new in A:
    add(M(i, what, one(G, old, new)))
    if i == "Q24c":
        MUTANTS[-1].equiv = "the guard realpath-resolves its cwd value itself and its patterns are suffix patterns, so the gate's text and the resolved path give the same verdict"


# --- the spawn and the status mapping ---------------------------------------------------------
E = [
    ("E01", "env not scrubbed", "env=scrubbed_env(), ", "env=dict(os.environ), "),
    ("E02", "env scrub bypassed with an empty extra that restores the process env", "env=scrubbed_env(), ", "env={**scrubbed_env(), **os.environ}, "),
    ("E03", "gate timeout ignored (budget cap lost)", "timeout_s=timeout_s, cwd=str(plan.cwd)", "timeout_s=gate.timeout_s, cwd=str(plan.cwd)"),
    ("E04", "timeout x100", "timeout_s=timeout_s, cwd=str(plan.cwd)", "timeout_s=timeout_s * 100, cwd=str(plan.cwd)"),
    ("E05", "no practical timeout", "timeout_s=timeout_s, cwd=str(plan.cwd)", "timeout_s=1e9, cwd=str(plan.cwd)"),
    ("E06", "cwd not passed", "timeout_s=timeout_s, cwd=str(plan.cwd)", "timeout_s=timeout_s, cwd=None"),
    ("E07", "cwd is the process folder", "timeout_s=timeout_s, cwd=str(plan.cwd)", "timeout_s=timeout_s, cwd=os.getcwd()"),
    ("E08", "FileNotFoundError text lost", "    except FileNotFoundError:", "    except KeyError:"),
    ("E09", "PermissionError text lost", "    except PermissionError:", "    except KeyError:"),
    ("E10", "other spawn errors escape", "    except Exception as exc:  # noqa: BLE001 - a spawn failure is an error, never a pass", "    except OSError as exc:  # noqa: BLE001"),
    ("E11", "KeyboardInterrupt swallowed", "    except Exception as exc:  # noqa: BLE001 - a spawn failure is an error, never a pass", "    except BaseException as exc:  # noqa: BLE001"),
    ("E12", "exception text in the message", 'f"could not start ({type(exc).__name__})"', 'f"could not start ({exc})"'),
    ("E13", "timeout flag ignored", "    if res.timed_out:", "    if False:"),
    ("E14", "exit 0 outranks the timeout flag", "    if res.timed_out:", "    if res.exit_code == 0:\n        return done(\"pass\", 0, \"\", out, err, cut)\n    if res.timed_out:"),
    ("E15", "missing exit status not handled", "    if res.exit_code is None:", "    if False:"),
    ("E16", "pass when exit <= 0", "    if res.exit_code == 0:", "    if res.exit_code <= 0:"),
    ("E17", "pass when exit != 0", "    if res.exit_code == 0:", "    if res.exit_code != 0:"),
    ("E18", "pass when exit is 0 or 1", "    if res.exit_code == 0:", "    if res.exit_code in (0, 1):"),
    ("E19", "signal text on positive codes", "if res.exit_code < 0 else", "if res.exit_code > 0 else"),
    ("E20", "failure status named error", 'return done("fail", res.exit_code, why, out, err, cut)', 'return done("error", res.exit_code, why, out, err, cut)'),
    ("E21", "timeout status named fail", 'return done("timeout", None,', 'return done("fail", None,'),
    ("E22", "pass status on a timeout", 'return done("timeout", None,', 'return done("pass", None,'),
    ("E23", "tails not redacted", "    cleaned = redact_secrets(text)[0]", "    cleaned = text"),
    ("E24", "head instead of tail", "return cleaned[-TAIL_CHARS:],", "return cleaned[:TAIL_CHARS],"),
    ("E25", "tail flag: > becomes >=", "len(cleaned) > TAIL_CHARS", "len(cleaned) >= TAIL_CHARS"),
    ("E26", "tail flag on the unredacted length", "len(cleaned) > TAIL_CHARS", "len(text) > TAIL_CHARS"),
    ("E27", "cut before redaction", "    cleaned = redact_secrets(text)[0]\n    return cleaned[-TAIL_CHARS:], len(cleaned) > TAIL_CHARS", "    cleaned = redact_secrets(text[-TAIL_CHARS:])[0]\n    return cleaned, len(text) > TAIL_CHARS"),
    ("E28", "capture truncation flag ignored", "cut = res.truncated or cut_out or cut_err", "cut = cut_out or cut_err"),
    ("E29", "stdout cut flag ignored", "cut = res.truncated or cut_out or cut_err", "cut = res.truncated or cut_err"),
    ("E30", "stderr cut flag ignored", "cut = res.truncated or cut_out or cut_err", "cut = res.truncated or cut_out"),
    ("E31", "cut flags and-ed", "cut = res.truncated or cut_out or cut_err", "cut = res.truncated or (cut_out and cut_err)"),
    ("E32", "stderr tail not redacted", "    err, cut_err = _tail(res.stderr)", "    err, cut_err = res.stderr[-TAIL_CHARS:], len(res.stderr) > TAIL_CHARS"),
    ("E33", "stdout tail not redacted", "    out, cut_out = _tail(res.stdout)", "    out, cut_out = res.stdout[-TAIL_CHARS:], len(res.stdout) > TAIL_CHARS"),
    ("E34", "negative duration", "round(time.monotonic() - start, 3)", "round(start - time.monotonic(), 3)"),
    ("E35", "stdout and stderr swapped in the result", "return GateResult(gate.id, status, code, elapsed, out, err, truncated, message)", "return GateResult(gate.id, status, code, elapsed, err, out, truncated, message)"),
    ("E36", "exit code dropped", "return GateResult(gate.id, status, code, elapsed, out, err, truncated, message)", "return GateResult(gate.id, status, None, elapsed, out, err, truncated, message)"),
    ("E37", "gate id replaced", "return GateResult(gate.id, status, code,", 'return GateResult("x", status, code,'),
    ("E38", "spawn failure reported as pass", 'return done("error", None, "executable or folder not found")', 'return done("pass", None, "executable or folder not found")'),
    ("E39", "not-executable reported as fail", 'return done("error", None, "not executable or not permitted")', 'return done("fail", None, "not executable or not permitted")'),
    ("E40", "generic spawn failure reported as pass", 'return done("error", None, f"could not start', 'return done("pass", None, f"could not start'),
]
for i, what, old, new in E:
    add(M(i, what, one(G, old, new)))

# --- run_gates, exit code, report --------------------------------------------------------------
F = [
    ("F01", "empty gate list allowed", "    if not gates:\n        raise ValueError", "    if False:\n        raise ValueError"),
    ("F34", "run_gates allows shell by default", "    allow_shell: bool = False,\n    total_s", "    allow_shell: bool = True,\n    total_s"),
    ("F02", "shell always allowed", "plan_gate(g, ws, allow_shell) for g in gates", "plan_gate(g, ws, True) for g in gates"),
    ("F03", "shell never allowed", "plan_gate(g, ws, allow_shell) for g in gates", "plan_gate(g, ws, False) for g in gates"),
    ("F04", "refusal only when every gate is refused", "    if len(ready) != len(plans):", "    if not ready:"),
    ("F05", "refusals never stop the run", "    if len(ready) != len(plans):", "    if False:"),
    ("F06", "refused gate reported as error", '_skipped(g.id, "policy-error", p)', '_skipped(g.id, "error", p)'),
    ("F07", "skipped gate reported as policy-error", '_skipped(g.id, "not-run", "another gate was refused")', '_skipped(g.id, "policy-error", "another gate was refused")'),
    ("F08", "skipped gate reported as pass", '_skipped(g.id, "not-run", "another gate was refused")', '_skipped(g.id, "pass", "another gate was refused")'),
    ("F09", "deadline in the past", "deadline = time.monotonic() + total_s", "deadline = time.monotonic() - total_s"),
    ("F10", "budget: <= becomes <", "        if remaining <= 0:", "        if remaining < 0:"),
    ("F11", "budget: skips under one second left", "        if remaining <= 0:", "        if remaining <= 1:"),
    ("F12", "budget check removed", "        if remaining <= 0:", "        if False:"),
    ("F13", "per-gate timeout: max", "min(g.timeout_s, remaining)", "max(g.timeout_s, remaining)"),
    ("F14", "per-gate timeout: gate only", "min(g.timeout_s, remaining)", "g.timeout_s"),
    ("F15", "per-gate timeout: remaining only", "min(g.timeout_s, remaining)", "remaining"),
    ("F16", "budget-skipped gate reported as pass", '_skipped(g.id, "not-run", "time budget used up")', '_skipped(g.id, "pass", "time budget used up")'),
    ("F17", "budget-skipped gates vanish (break)", '            results.append(_skipped(g.id, "not-run", "time budget used up"))', '            break'),
    ("F18", "fail-fast: stop at the first non-pass", "            results.append(_run_one(g, p, min(g.timeout_s, remaining)))", "            results.append(_run_one(g, p, min(g.timeout_s, remaining)))\n            if results[-1].status != \"pass\":\n                break"),
    ("F19", "gates run in reverse order", "for g, p in zip(gates, ready, strict=True):\n        remaining", "for g, p in reversed(list(zip(gates, ready, strict=True))):\n        remaining"),
    ("F20", "gates run sorted by id", "for g, p in zip(gates, ready, strict=True):\n        remaining", "for g, p in sorted(zip(gates, ready, strict=True), key=lambda t: t[0].id):\n        remaining"),
    ("F21", "duplicate ids collapse in the report", "    return _report(results)\n\n\ndef exit_code", "    return _report(list({r.id: r for r in results}.values()))\n\n\ndef exit_code"),
    ("F22", "report order from a set", "    return _report(results)\n\n\ndef exit_code", "    return _report(list({*results}))\n\n\ndef exit_code"),
    ("F23", "ok run reports exit 1", "    if report.ok:\n        return 0", "    if report.ok:\n        return 1"),
    ("F24", "policy error maps to 1", "    return 2 if any(r.status == \"policy-error\" for r in report.gates) else 1", "    return 1"),
    ("F25", "everything non-ok maps to 2", "    return 2 if any(r.status == \"policy-error\" for r in report.gates) else 1", "    return 2"),
    ("F26", "policy-error check on fail", 'any(r.status == "policy-error" for r in report.gates)', 'any(r.status == "fail" for r in report.gates)'),
    ("F27", "exit 0 whenever any gate passed", "    if report.ok:\n        return 0", "    if report.passed:\n        return 0"),
    ("F28", "ok when any gate passed", "total > 0 and passed == total)", "total > 0 and passed > 0)"),
    ("F29", "ok when nothing failed (not-run counts as ok)", "sum(r.status == \"pass\" for r in results)\n    total = len(results)\n    return GateReport(tuple(results), passed, total - passed, total, total > 0 and passed == total)", "sum(r.status == \"pass\" for r in results)\n    total = len(results)\n    return GateReport(tuple(results), passed, total - passed, total, total > 0 and not any(r.status in ('fail', 'error', 'timeout', 'policy-error') for r in results))"),
    ("F30", "ok on an empty report", "total > 0 and passed == total)", "passed == total)"),
    ("F31", "pass counted for not-run too", 'sum(r.status == "pass" for r in results)', 'sum(r.status in ("pass", "not-run") for r in results)'),
    ("F32", "failed count is total", "GateReport(tuple(results), passed, total - passed,", "GateReport(tuple(results), passed, total,"),
    ("F33", "report keeps only the first gate", "return GateReport(tuple(results),", "return GateReport(tuple(results[:1]),"),
]
for i, what, old, new in F:
    add(M(i, what, one(G, old, new)))
for m in MUTANTS:
    if m.id == "F22":
        m.seeds = True

# --- main / CLI --------------------------------------------------------------------------------
C = [
    ("M01", "--allow-shell inverted", '        action="store_true",\n        help="honour', '        action="store_false",\n        help="honour'),
    ("M02", "shell always allowed from the CLI", "allow_shell=args.allow_shell", "allow_shell=True"),
    ("M03", "--root ignored", "Workspace(args.root if args.root is not None else os.getcwd())", "Workspace(os.getcwd())"),
    ("M04", "default root is not the current folder", "Workspace(args.root if args.root is not None else os.getcwd())", "Workspace(args.root)"),
    ("M05", "root errors not handled as such", "except (GateFileError, FileNotFoundError, NotADirectoryError) as exc:", "except GateFileError as exc:"),
    ("M06", "unexpected errors escape", "    except Exception as exc:  # noqa: BLE001 - any other failure is exit 2, never 0 or 1", "    except ValueError as exc:  # noqa: BLE001"),
    ("M07", "gate-file error exits 1", "return 2 if _emit(str(exc)) else _stdout_lost()", "return 1 if _emit(str(exc)) else _stdout_lost()"),
    ("M08", "unexpected error exits 1", 'return 2 if _emit(f"Gates could not run ({type(exc).__name__}).") else _stdout_lost()', 'return 1 if _emit(f"Gates could not run ({type(exc).__name__}).") else _stdout_lost()'),
    ("M09", "unexpected error text echoed", '_emit(f"Gates could not run ({type(exc).__name__}).")', '_emit(f"Gates could not run ({exc}).")'),
    ("M10", "exit code is 0/1 only", "    code = exit_code(report)", "    code = 0 if report.ok else 1"),
    ("M11", "a lost report still returns the gate code", "return code if _emit(json.dumps(out, indent=2)) else _stdout_lost()", "return (_emit(json.dumps(out, indent=2)), code)[1]"),
    ("M12", "report kind renamed", '"kind": "gates"', '"kind": "results"'),
    ("M13", "report schema_version 2", 'out = {"schema_version": SCHEMA_VERSION,', 'out = {"schema_version": 2,'),
    ("M14", "report has C4 results key", '"kind": "gates", **asdict(report)}', '"kind": "gates", **asdict(report), "results": [{"case_id": g.id, "passed": g.status == "pass"} for g in report.gates]}'),
    ("M15", "emit catches OSError only", "    except Exception:  # noqa: BLE001 - stdout lost: the caller still exits 2, never 0 or 1", "    except OSError:  # noqa: BLE001"),
    ("M16", "emit reports success after a loss", "        return False\n    return True", "        return True\n    return True"),
    ("M17", "emit does not flush", "        print(text)\n        sys.stdout.flush()", "        print(text)"),
    ("M18", "emit does not print", "        print(text)\n        sys.stdout.flush()", "        sys.stdout.flush()"),
    ("M19", "lost stdout not parked (exit 120 at interpreter exit)", "_stdout_lost()", "2", 3),
    ("M23", "report JSON not ASCII-escaped", "json.dumps(out, indent=2)", "json.dumps(out, indent=2, ensure_ascii=False)"),
    ("M20", "one positional gate file only (nargs *)", 'ap.add_argument("gate_file")', 'ap.add_argument("gate_file", nargs="*")'),
    ("M21", "gate file path ignored for a fixed name", "load_gate_file(args.gate_file)", 'load_gate_file("gates.json")'),
    ("M22", "gates run before the root is checked (order)", "        gates = load_gate_file(args.gate_file)\n        ws = Workspace(", "        ws = Workspace("),
]
for it in C:
    i, what, old, new, *n = it
    if i == "M22":
        add(M(i, what, one(G, "            gates = load_gate_file(args.gate_file)\n", "") + one(G, "            report = run_gates(gates, ws,", "            gates = load_gate_file(args.gate_file)\n            report = run_gates(gates, ws,"),
              equiv="the root is checked first or second: both failures print an exit-2 message, and no gate has run before either check"))
    else:
        add(M(i, what, one(G, old, new, *(n or [1]))))

# --- signals sent to the runner itself ------------------------------------------------------
HS = '        for old_sig, previous in saved:  # None = installed from C: SIG_DFL is the closest restore\n'
RESTORE = "            signal.signal(old_sig, signal.SIG_DFL if previous is None else previous)\n"
GS = [
    ("G01", "handlers never installed", "        with _signals_raise():\n", "        if True:\n"),
    ("G02", "signal exits 0", "    raise SystemExit(128 + signum)", "    raise SystemExit(0)"),
    ("G03", "signal exits 1", "    raise SystemExit(128 + signum)", "    raise SystemExit(1)"),
    ("G04", "signal exits 128", "    raise SystemExit(128 + signum)", "    raise SystemExit(128)"),
    ("G05", "signal exits with the bare signal number", "    raise SystemExit(128 + signum)", "    raise SystemExit(signum)"),
    ("G06", "handlers not restored", RESTORE, "            pass\n"),
    ("G07", "off-main-thread ValueError not handled", "    except ValueError:  # not the main thread: leave the handlers alone", "    except KeyError:  # not the main thread: leave the handlers alone"),
    ("G08", "SIGHUP not handled", "HANDLED_SIGNALS: Final = (signal.SIGTERM, signal.SIGHUP)", "HANDLED_SIGNALS: Final = (signal.SIGTERM,)"),
    ("G08b", "SIGTERM not handled", "HANDLED_SIGNALS: Final = (signal.SIGTERM, signal.SIGHUP)", "HANDLED_SIGNALS: Final = (signal.SIGHUP,)"),
    ("G08c", "SIGINT handled instead of SIGHUP", "HANDLED_SIGNALS: Final = (signal.SIGTERM, signal.SIGHUP)", "HANDLED_SIGNALS: Final = (signal.SIGTERM, signal.SIGINT)"),
    ("G09", "handler raises KeyboardInterrupt", "    raise SystemExit(128 + signum)", "    raise KeyboardInterrupt"),
    ("G10", "run_gates outside the handlers' scope", "            report = run_gates(gates, ws, allow_shell=args.allow_shell)\n    except (GateFileError", "        report = run_gates(gates, ws, allow_shell=args.allow_shell)\n    except (GateFileError"),
    ("G11", "restore always to the default handler", RESTORE, "            signal.signal(old_sig, signal.SIG_DFL)\n"),
    ("G12", "handler swallows the signal", "    raise SystemExit(128 + signum)", "    return None"),
    ("G13", "None (a C-installed handler) not guarded on restore", RESTORE, "            signal.signal(old_sig, previous)\n"),
    ("G14", "only the first handler restored", HS, "        for old_sig, previous in saved[:1]:  # None = installed from C: SIG_DFL is the closest restore\n"),
]
for i, what, old, new in GS:
    add(M(i, what, one(G, old, new)))

# --- a shell is not a non-shell gate (ATK1) --------------------------------------------------
HOLD = "        if not gate.shell:  # needs the gate's cwd: the child resolves argv[0] from there\n"
SN = "    if names & SHELL_NAMES or first in SHELL_RUNNERS:\n"
WR = "    if first in WRAPPERS and any(_base(a) in SHELL_NAMES for a in argv[1:]):\n"
HS_ = [
    ("H01", "shell check never called", HOLD, "        if False:\n"),
    ("H02", "shell check also applied to declared shell gates", HOLD, "        if True:\n"),
    ("H03", "shell check only on declared shell gates", HOLD, "        if gate.shell:\n"),
    ("H04", "name not lower-cased", '    name = word.rsplit("/", 1)[-1].lower()\n', '    name = word.rsplit("/", 1)[-1]\n'),
    ("H05", ".exe not stripped", '    return name.removesuffix(".exe")\n', "    return name\n"),
    ("H06", "directory part not stripped", '    name = word.rsplit("/", 1)[-1].lower()\n', "    name = word.lower()\n"),
    ("H07", "resolved path (realpath) ignored", "            names.add(_base(found))\n", "            pass\n"),
    ("H08", "bare name not looked up on PATH", "    for entry in os.get_exec_path():\n", "    for entry in ():\n"),
    ("H09", "path form not resolved", '    if "/" in word:\n', "    if False:\n"),
    ("H10", "lexical name ignored", "    names = {first}\n", "    names = set()\n"),
    ("H11", "shell-running programs (su, watch) not refused", SN, "    if names & SHELL_NAMES:\n"),
    ("H12", "wrappers never checked", WR, "    if False:\n"),
    ("H13", "wrapper checks only the first argument", WR, "    if first in WRAPPERS and any(_base(a) in SHELL_NAMES for a in argv[1:2]):\n"),
    ("H14", "wrapper refused without a shell argument", WR, "    if first in WRAPPERS:\n"),
    ("H15", "wrapper argument compared without its basename", WR, "    if first in WRAPPERS and any(a in SHELL_NAMES for a in argv[1:]):\n"),
    ("H16", "any program is checked like a wrapper", WR, "    if any(_base(a) in SHELL_NAMES for a in argv[1:]):\n"),
    ("H17", "wrapper arguments compared case-sensitively", WR, "    if first in WRAPPERS and any(a.rsplit('/', 1)[-1] in SHELL_NAMES for a in argv[1:]):\n"),
    ("H18", "refusal echoes the executable", '        return "the executable is a shell; declare shell: true and pass --allow-shell"\n', '        return f"the executable {argv[0]} is a shell; declare shell: true and pass --allow-shell"\n'),
    ("H19", "wrapper refusal echoes the arguments", '        return "a wrapper is given a shell; declare shell: true and pass --allow-shell"\n', '        return f"a wrapper is given {argv[1:]}; declare shell: true and pass --allow-shell"\n'),
    ("H20", "shell names matched by prefix", SN, "    if any(n.startswith(s) for n in names for s in SHELL_NAMES) or first in SHELL_RUNNERS:\n"),
    ("H21", "python treated as a shell", SN, '    if names & (SHELL_NAMES | {"python"}) or first in SHELL_RUNNERS:\n'),
    ("H22", "ssh-keygen treated as a shell (prefix of a name)", SN, '    if names & SHELL_NAMES or first in SHELL_RUNNERS or first == "ssh-keygen":\n'),
    ("H23", "refusal text drops the way out (--allow-shell)", '        return "the executable is a shell; declare shell: true and pass --allow-shell"\n', '        return "the executable is a shell"\n'),
]
# --- rounds 3 to 3c (ATK4, ATK5, D1): ONE physical walk, no normalisation, no ".." ---------------
WALK = "        return _walk(os.path.join(cwd, word))\n"
PBASE = "        base = _walk(os.path.join(cwd, entry))\n"
RS = [
    ("T01", "relative path resolved against the runner's cwd", WALK, "        return _walk(os.path.abspath(word))\n"),
    ("T02", "PATH search resolved from the runner's cwd", PBASE, "        base = _walk(os.path.join(os.getcwd(), entry))\n"),
    ("T02b", "PATH entry not joined onto any cwd", PBASE, "        base = _walk(entry)\n"),
    ("T03", "non-executable files found on PATH", " and os.access(candidate, os.X_OK)", ""),
    ("T04", "directories and missing files found on PATH", "        if os.path.isfile(candidate) and", "        if True and"),
    ("T05", "PATH hit not walked before the file test (r48, r49: a hit that is a link into /proc)", "        candidate = _walk(os.path.join(base, word))  # a hit that is a link into /proc is refused\n", "        candidate = os.path.join(base, word)\n"),
    ("T05b", "PATH hit returned unresolved (a link of any name to a shell is missed)", "            return candidate\n", "            return os.path.join(base, word)\n"),
    ("T06", "PATH fixed instead of the process PATH", "    for entry in os.get_exec_path():\n", '    for entry in ("/usr/bin", "/bin"):\n'),
    ("T07", "path form not resolved through symlinks", WALK, "        return os.path.join(cwd, word)\n"),
    ("T08", "slash test only for absolute words", '    if "/" in word:\n', '    if word.startswith("/"):\n'),
    ("T09", "empty PATH entries skipped", "    for entry in os.get_exec_path():\n", "    for entry in [e for e in os.get_exec_path() if e]:\n"),
    ("T10", "relative PATH entries skipped", "    for entry in os.get_exec_path():\n", "    for entry in [e for e in os.get_exec_path() if os.path.isabs(e)]:\n"),
    ("T11", "only the first PATH entry searched", "    for entry in os.get_exec_path():\n", "    for entry in os.get_exec_path()[:1]:\n"),
    ("T12", "gate cwd replaced by the runner cwd for the whole check", "        refusal = _shell_refusal(argv, cwd)\n", "        refusal = _shell_refusal(argv, Path.cwd())\n"),
    ("T13", "last PATH hit instead of the first (the judge's K08)", "    for entry in os.get_exec_path():\n", "    for entry in reversed(os.get_exec_path()):\n"),
]
for i, what, old, new in RS:
    add(M(i, what, one(G, old, new)))

WK = "        if _opaque(nxt):\n            raise _Refused(OPAQUE_MSG)\n"
VS = [
    ("V08", "/proc not an opaque root", 'OPAQUE_ROOTS: Final = ("/proc", "/dev")', 'OPAQUE_ROOTS: Final = ("/dev",)'),
    ("V09", "/dev not an opaque root", 'OPAQUE_ROOTS: Final = ("/proc", "/dev")', 'OPAQUE_ROOTS: Final = ("/proc",)'),
    ("V10", "the root itself (/proc, /dev) not refused", "path == root or path.startswith", "path.startswith"),
    ("V12", "every link refused after the first (limit 0)", "            if links > 40:\n", "            if links > 0:\n"),
    ("V15", "refusal exception not caught", "    except _Refused as exc:\n", "    except ZeroDivisionError:\n"),
    ("V16", "refusal echoes the word", "        return str(exc)\n", "        return f\"{str(exc)} {argv[0]}\"\n"),
    ("V25", "root prefix without the slash (QA Q25: /developer refused)", 'path.startswith(root + "/")', "path.startswith(root)"),
    ("W01", "dotdot check on the word removed", "    _no_dotdot(word)\n", ""),
    ("W02", "dotdot check on a PATH entry removed", "        _no_dotdot(entry)\n", ""),
    ("W03", "dotdot only for the bare word ..", 'if ".." in path.split("/"):', 'if path == "..":'),
    ("W04", "dotdot checked AFTER normalisation (the D1 root cause)", 'if ".." in path.split("/"):', 'if ".." in os.path.normpath(path).split("/"):'),
    ("W05", "dotdot refusal echoes the path", "        raise _Refused(DOTDOT_MSG)\n", "        raise _Refused(f\"{DOTDOT_MSG}: {path}\")\n"),
    ("W06", "no component is checked against /proc and /dev", WK, ""),
    ("W07", "links never examined", "        if os.path.islink(nxt):\n", "        if False:\n"),
    ("W08", "link target not pushed onto the walk", "            todo.extend(target.split(\"/\")[::-1])  # a relative target starts from the link's folder\n", "            pass\n"),
    ("W09", "link target pushed in the wrong order", "target.split(\"/\")[::-1])  # a relative", "target.split(\"/\"))  # a relative"),
    ("W10", "absolute target does not restart at /", "            if target.startswith(\"/\"):\n                cur = \"/\"\n", ""),
    ("W11", "every target restarts at / (relative targets resolved from the root)", "            if target.startswith(\"/\"):\n", "            if True:\n"),
    ("W12", "the walk never advances", "        cur = nxt\n    return cur\n", "        cur = cur\n    return cur\n"),
    ("W13", "OSError while resolving accepted (fail open)", '        return "the executable path could not be examined"\n', "        pass\n"),
    ("W14", "loop limit message missing (loop accepted as a plain refusal text)", 'LOOP_MSG: Final = "the executable path has a link loop or more than 40 links"', 'LOOP_MSG: Final = "refused"'),
    ("W15", "shell check on the lexical word only (resolution dropped)", "        found = _resolve(argv[0], cwd)\n", "        found = None\n"),
    ("W16", "the '.' component not skipped", 'if part in ("", "."):', 'if part == "":'),
    ("W17", "a '..' from a link target is joined, not applied (the walk's own D1)", '        if part == "..":\n            cur = os.path.dirname(cur)  # "/" stays "/", as in the kernel\n            continue\n', ""),
    ("W18", "a '..' from a link target is ignored", '            cur = os.path.dirname(cur)  # "/" stays "/", as in the kernel\n', "            pass\n"),
    ("W19", "a '..' from a link target goes to the root", '            cur = os.path.dirname(cur)  # "/" stays "/", as in the kernel\n', '            cur = "/"\n'),
    ("W21", "the walk starts at // (a leading double slash is not seen as the root: QA Q26's form)", '    cur, links = "/", 0\n', '    cur, links = "//", 0\n'),
    ("W22", "an empty component (trailing slash, //) is not skipped: the resolved path keeps a trailing slash and its basename is empty", 'if part in ("", "."):', 'if part == ".":'),
    ("W20", "a '..' from a link target is applied to the path text (normpath), not the folder reached", '            cur = os.path.dirname(cur)  # "/" stays "/", as in the kernel\n', "            cur = os.path.normpath(os.path.join(cur, part))\n"),
]
for i, what, old, new in VS:
    add(M(i, what, one(G, old, new)))
W20_EQUIV = "the folder reached holds no link and no .., so normpath(join(cur, '..')) is dirname(cur): the same value"
for _m in MUTANTS:
    if _m.id == "W20":
        _m.equiv = W20_EQUIV

for i, what, old, new in HS_:
    add(M(i, what, one(G, old, new)))
for n in sorted(["sh", "bash", "dash", "ash", "ksh", "mksh", "pdksh", "posh", "yash", "zsh", "fish", "csh", "tcsh", "rbash"]):
    add(M(f"H3-{n}", f"shell name {n} dropped from the executable check",
          one(G, SN, f'    if names & (SHELL_NAMES - {{"{n}"}}) or first in SHELL_RUNNERS:\n')))
    add(M(f"H4-{n}", f"shell name {n} dropped from the wrapper argument check",
          one(G, WR, WR.replace("in SHELL_NAMES", f'in (SHELL_NAMES - {{"{n}"}})'))))
for n in ["su", "watch"]:
    add(M(f"H5-{n}", f"{n} dropped from SHELL_RUNNERS",
          one(G, SN, f'    if names & SHELL_NAMES or first in (SHELL_RUNNERS - {{"{n}"}}):\n')))
for n in sorted(["env", "xargs", "busybox", "toybox", "nohup", "exec", "command", "builtin", "sudo", "doas", "timeout", "nice", "ionice", "setsid", "stdbuf", "chroot", "find", "flock", "unshare", "strace", "time", "chrt", "taskset", "script", "runuser", "setpriv", "nsenter", "ssh", "parallel"]):
    add(M(f"H6-{n}", f"wrapper {n} dropped", one(G, WR, WR.replace("first in WRAPPERS", 'first in (WRAPPERS - {"%s"})' % n))))

# --- stream.py (existing module, one new keyword) -----------------------------------------------
add(M("S01", "stream: cwd not passed to Popen", one(S, "        cwd=cwd,\n", "")))
add(M("S02", "stream: stdin inherited", one(S, "        stdin=subprocess.DEVNULL,\n", "")))
add(M("S03", "stream: no new session (no process group)", one(S, "        start_new_session=True,\n", "        start_new_session=False,\n")))
add(M("S04", "stream: kill the child only, not the group", one(S, "os.killpg(proc.pid, signal.SIGKILL)", "proc.kill()")))
add(M("S05", "stream: shell=True", one(S, "        cwd=cwd,\n", "        cwd=cwd,\n        shell=True,\n")))
add(M("S07", "stream: stdin is an open pipe", one(S, "        stdin=subprocess.DEVNULL,\n", "        stdin=subprocess.PIPE,\n")))
for k, name in enumerate(["KEY", "PASSWORD", "SECRET", "TOKEN"], 8):
    rest = "|".join(n for n in ["KEY", "PASSWORD", "SECRET", "TOKEN"] if n != name)
    add(M(f"S{k:02d}", f"stream: {name} dropped from the env scrub", one(S, 'r"KEY|PASSWORD|SECRET|TOKEN"', f'r"{rest}"')))
add(M("S12", "stream: env scrub is case-sensitive", one(S, 're.compile(r"KEY|PASSWORD|SECRET|TOKEN", re.IGNORECASE)', 're.compile(r"KEY|PASSWORD|SECRET|TOKEN")')))
add(M("S13", "stream: env not scrubbed at all", one(S, "env = {k: v for k, v in os.environ.items() if not SENSITIVE_ENV.search(k)}", "env = dict(os.environ)")))
add(M("S14", "stream: cwd defaults to the filesystem root", one(S, "    cwd: str | None = None,\n", '    cwd: str | None = "/",\n')))
add(M("S15", "stream: a missing cwd falls back to the filesystem root", one(S, "        cwd=cwd,\n", '        cwd=cwd or "/",\n')))
add(M("S06", "stream: cwd from the process folder", one(S, "        cwd=cwd,\n", "        cwd=os.getcwd(),\n")))

# --- equivalent mutants (expected to survive; the reason is the claim) ---------------------------
add(M("Z01", "zip(strict=True) -> False in the refused branch", one(G, "for g, p in zip(gates, plans, strict=True)", "for g, p in zip(gates, plans, strict=False)"),
      equiv="plans has one entry per gate, so strict only guards an impossible length mismatch"))
add(M("Z02", "zip(strict=True) -> False in the run loop", one(G, "for g, p in zip(gates, ready, strict=True):", "for g, p in zip(gates, ready, strict=False):"),
      equiv="ready has one entry per gate when the refusal branch did not return"))
add(M("Z03", "isinstance(p, str) -> not isinstance(p, Plan)", one(G, "if isinstance(p, str)\n                    else _skipped", "if not isinstance(p, Plan)\n                    else _skipped"),
      equiv="plan_gate returns exactly Plan or str"))
add(M("Z04", "timeout default via entry.get", one(G, 'timeout = _timeout(entry["timeout_s"]) if "timeout_s" in entry else DEFAULT_TIMEOUT_S', 'timeout = _timeout(entry.get("timeout_s", DEFAULT_TIMEOUT_S))'),
      equiv="an explicit null gives get() -> None -> _timeout(None) -> None, the same refusal"))
add(M("Z05", "SandboxDenied -> OSError in the cwd except", one(G, "        except SandboxDenied as exc:", "        except OSError as exc:"),
      equiv="SandboxDenied subclasses PermissionError, an OSError, and exc.reason exists on it"))


# ------------------------------------------------------------------------------------------------
def pycopy(tree: Path, dest: Path) -> None:
    tar = dest.parent / (dest.name + ".tar")
    skip = (".git", "__pycache__", ".pytest_cache", ".venv", "references")
    with tarfile.open(tar, "w") as t:
        for item in sorted(tree.iterdir()):
            if item.name in skip:
                continue
            t.add(item, arcname=item.name, filter=lambda ti: None if any(s in ti.name.split("/") for s in skip) else ti)
    with tarfile.open(tar) as t:
        t.extractall(dest, filter="data")
    tar.unlink()


def run_pytest(copy: Path, py: str, seed: str | None) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUNBUFFERED", "PYTHONPATH", "PYTHONHASHSEED")}
    env["PYTHONPATH"] = str(copy / "src")
    if seed is not None:
        env["PYTHONHASHSEED"] = seed
    try:
        p = subprocess.run([py, "-B", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "--no-header", *TESTS],
                           cwd=copy, env=env, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired as exc:
        return 124, f"TIMEOUT {exc.timeout}s"
    return p.returncode, p.stdout + p.stderr


def check_path(copy: Path, py: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(copy / "src")}
    out = subprocess.run([py, "-B", "-c", "import master_finhub.evals.gates as m; print(m.__file__)"],
                         cwd=copy, env=env, capture_output=True, text=True, check=True).stdout.strip()
    assert out.startswith(str(copy)), f"imports {out}, not the copy"


def failed_names(outputs: list[str]) -> list[str]:
    names = {re.sub(r".*::", "", ln.split(" ")[1]).split("[")[0] for o in outputs for ln in o.splitlines() if ln.startswith("FAILED ")}
    return sorted(names)


def evaluate(m: M, tree: Path, scratch: Path, py: str) -> tuple[str, int, str, list[str]]:
    d = Path(tempfile.mkdtemp(prefix=f"c9_{m.id}_", dir=scratch))
    pycopy(tree, d / "t")
    copy = d / "t"
    delta = 0
    for edit in m.edits:
        f, old, new = edit[:3]
        want = edit[3] if len(edit) > 3 else 1
        path = copy / f
        text = path.read_text()
        assert text.count(old) == want, f"{m.id}: old text occurs {text.count(old)} times in {f} (want {want})"
        mutated = text.replace(old, new)
        assert mutated != text, f"{m.id}: no-op mutation"
        delta += sum(1 for ln in difflib.unified_diff(text.splitlines(), mutated.splitlines(), lineterm="") if ln[:1] in "+-" and ln[:3] not in ("+++", "---"))
        path.write_text(mutated)
        assert path.read_text() != text
    check_path(copy, py)
    if os.environ.get("C9_DRY"):
        shutil.rmtree(d, ignore_errors=True)
        return "DRY", delta, "", []
    seeds = [str(s) for s in range(40)] if m.seeds else [None]
    results = [run_pytest(copy, py, s) for s in seeds]
    shutil.rmtree(d, ignore_errors=True)
    dead = [rc != 0 for rc, _ in results]
    failed = failed_names([o for _, o in results])
    status = "KILLED" if all(dead) else ("SURVIVED" if not any(dead) else "FLAKY-PARTIAL")
    if status == "KILLED" and failed and set(failed) <= TIMING:
        status = "TIMING-ONLY"
    if any(o.startswith("TIMEOUT ") for _, o in results):
        status = status + "+TIMEOUT"
    return status, delta, f"x{len(seeds)} seeds" if m.seeds else "1 run", failed


def main() -> int:
    tree, scratch = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    py = sys.argv[3] if len(sys.argv) > 3 else sys.executable
    scratch.mkdir(parents=True, exist_ok=True)
    only = os.environ.get("C9_ONLY")
    if only:
        MUTANTS[:] = [m for m in MUTANTS if m.id.startswith(only)]
    ids = [m.id for m in MUTANTS]
    assert len(ids) == len(set(ids)), "duplicate mutant ids"
    jobs = int(os.environ.get("C9_JOBS", "4"))
    if not os.environ.get("C9_DRY"):
        base = Path(tempfile.mkdtemp(prefix="c9ctl_", dir=scratch))
        pycopy(tree, base / "t")
        check_path(base / "t", py)
        rc, out = run_pytest(base / "t", py, None)
        print(f"CONTROL (unmutated copy, serial): rc={rc} {out.strip().splitlines()[-1]}", flush=True)
        if rc != 0:
            print(out[-3000:])
            return 2
    with ThreadPoolExecutor(jobs) as ex:
        res = list(ex.map(lambda m: evaluate(m, tree, scratch, py), MUTANTS))
    # serial re-run of the mutants that only timing-sensitive tests killed
    for k, (m, r) in enumerate(zip(MUTANTS, res)):
        if r[0].startswith("TIMING-ONLY"):
            again = evaluate(m, tree, scratch, py)
            res[k] = ("KILLED(rerun)" if again[0] in ("KILLED", "TIMING-ONLY") else "SURVIVED(rerun)", r[1], r[2], r[3])
    killed = surv_eq = bad = 0
    for m, (status, delta, tag, failed) in zip(MUTANTS, res):
        ok = status.startswith("KILLED") or status == "DRY"
        if ok:
            killed += 1
        elif m.equiv and status.startswith("SURVIVED"):
            surv_eq += 1
        else:
            bad += 1
        eq = f" [equivalent: {m.equiv}]" if m.equiv and status.startswith("SURVIVED") else ""
        print(f"{m.id:4} {status:16} diff-lines={delta:2} {tag:11} {m.what} -> {', '.join(failed[:3])}{'...' if len(failed) > 3 else ''}{eq}", flush=True)
    n = len(MUTANTS)
    print(f"TOTAL {n}: killed {killed}, survived-equivalent {surv_eq}, unexpected survivors/partial {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
