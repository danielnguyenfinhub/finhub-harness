"""C9 independent ReDoS sweep. Usage: PYTHONPATH=<tree>/src python 02_strategy-architect_C9_redos.py

gates.py has no regex of its own (a test pins `not hasattr(gates, "re")`). It does feed two
regex-bearing modules with attacker-influenced text, so this sweeps the ACTUAL code paths:
  1. redact_secrets (tools/secret_scan.py rule table) through a REAL gate run: a child prints a
     pathological shape of SIZE bytes, gates.run_gates captures the last 64,000 bytes and redacts.
     SIZE = 4096, 200,000 and 1,000,000.
  2. check_command (tools/safety.py regexes and lexer) through gates.plan_gate on command strings
     and argv lists at the size caps (4,096 characters per item; the joined line is capped at 10,000
     by the guard), and the loader on a 1 MB file (refused by size before any parsing).
Prints one row per (path, shape, size) with seconds; exits 1 if any row exceeds LIMIT seconds.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

from master_finhub.evals import gates as gm
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools.secret_scan import RULES

LIMIT = 5.0
PY = sys.executable
SIZES = (4096, 200_000, 1_000_000)
OUT_SHAPES = {
    "eyJ-repeat": "eyJ",
    "eyJ-dash-repeat": "eyJ-",
    "eyJ-dot-repeat": "eyJ.",
    "sk-repeat": "sk-",
    "sk-ant-repeat": "sk-ant-",
    "AKIA-repeat": "AKIA",
    "ghp_-repeat": "ghp_",
    "github_pat_-repeat": "github_pat_",
    "xox-repeat": "xoxb-",
    "Bearer-space-repeat": "Bearer ",
    "Bearer-then-token": "Bearer " + "A" * 15 + " ",
    "x-mcp-key-repeat": "x-mcp-key: ",
    "PEM-begin-repeat": "-----BEGIN PRIVATE KEY-----\n",
    "PEM-begin-no-end-after-text": "-----BEGIN RSA PRIVATE KEY-----" + "A" * 50 + "\n",
    "digits": "1234567890",
    "dashes": "-",
    "underscores": "_",
    "newlines": "\n",
    "spaces": " ",
    "token-chars": "aB3-_./+=~",
}
CMD_SHAPES = {
    "word": "a",
    "words": "a ",
    "single-quotes": "'",
    "double-quotes": '"',
    "backslashes": "\\",
    "dollar-paren": "$(",
    "semicolons": ";",
    "pipes": "|",
    "ampersands": "&",
    "tilde-slash": "~/",
    "assignments": "a=",
    "dashes": "-",
    "dot-dot": "../",
    "sudo-env": "env -u ",
    "paths": "/a",
    "ssh-ish": "/.ssh/x ",
    "unicode": "é",
    "dev-nodes": "/dev/sda ",
    "git-push": "git push -f ",
    "rm-flags": "rm -r -f ",
}


def fill(unit: str, size: int) -> str:
    return (unit * (size // len(unit) + 1))[:size]


def row(path: str, shape: str, size: int, seconds: float, note: str = "") -> bool:
    ok = seconds <= LIMIT
    print(f"{path:10} {shape:30} {size:>9} {seconds:8.3f}s {'ok' if ok else 'SLOW'} {note}", flush=True)
    return ok


def main() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        # 1. redaction behind a real gate run
        for name, unit in OUT_SHAPES.items():
            for size in SIZES:
                code = (
                    "import sys; u = " + repr(unit) + "; n = " + str(size)
                    + "; sys.stdout.write((u * (n // len(u) + 1))[:n])"
                )
                gate = gm.Gate("g1", None, (PY, "-c", code), False, 120.0, ".")
                start = time.monotonic()
                report = gm.run_gates([gate], ws, total_s=300)
                elapsed = time.monotonic() - start
                status = report.gates[0].status
                ok &= row("redact", name, size, elapsed, f"status={status} tail={len(report.gates[0].stdout_tail)}")
                ok &= status == "pass"
        # 2. the guard behind plan_gate (string, argv and shell forms) at the caps
        for name, unit in CMD_SHAPES.items():
            for size in (4096,):
                text = "x " + fill(unit, size - 2)
                for form, gate in (
                    ("string", gm.Gate("g", text, None, False, 5.0, ".")),
                    ("argv", gm.Gate("g", None, ("x", fill(unit, 4096)), False, 5.0, ".")),
                    ("argv-many", gm.Gate("g", None, ("x",) + (fill(unit, 30),) * 255, False, 5.0, ".")),
                    ("shell", gm.Gate("g", text, None, True, 5.0, ".")),
                ):
                    start = time.monotonic()
                    got = gm.plan_gate(gate, ws, True)
                    ok &= row(f"guard-{form}", name, size, time.monotonic() - start, type(got).__name__)
            for size in (200_000, 1_000_000):
                start = time.monotonic()
                a = gm.plan_gate(gm.Gate("g", "x " + fill(unit, size), None, False, 5.0, "."), ws, True)
                b = gm.plan_gate(gm.Gate("g", None, ("x", fill(unit, size)), False, 5.0, "."), ws, True)
                c = gm.plan_gate(gm.Gate("g", "x " + fill(unit, size), None, True, 5.0, "."), ws, True)
                refused = all(isinstance(r, str) and "too long" in r for r in (a, b, c))
                ok &= row("guard-big", name, size, time.monotonic() - start, f"refused-by-length={refused}")
                ok &= refused
        # 3. the loader on files at and above the cap
        for size in (4096, 262_144, 1_000_000):
            p = Path(tmp) / "g.json"
            body = json.dumps({"schema_version": 1, "gates": [{"id": "a", "command": "pytest -q"}]})
            p.write_text(body + " " * max(0, size - len(body)))
            start = time.monotonic()
            try:
                gm.load_gate_file(p)
                note = "loaded"
            except gm.GateFileError:
                note = "refused"
            ok &= row("loader", "padded-json", size, time.monotonic() - start, note)
        for size in (4096, 262_144, 1_000_000):
            p = Path(tmp) / "deep.json"
            p.write_text("[" * size)
            start = time.monotonic()
            try:
                gm.load_gate_file(p)
                note = "loaded"
            except gm.GateFileError:
                note = "refused"
            ok &= row("loader", "deep-nesting", size, time.monotonic() - start, note)
    # 4. the ACTUAL regexes directly, at the three sizes (the gate path above only ever shows
    #    redact_secrets the last 64,000 bytes; this feeds it the whole input)
    from master_finhub.tools.safety import check_command
    from master_finhub.tools.secret_scan import redact_secrets

    for name, unit in OUT_SHAPES.items():
        for size in SIZES:
            text = fill(unit, size)
            start = time.monotonic()
            cleaned, fired = redact_secrets(text)
            ok &= row("direct-rs", name, size, time.monotonic() - start, f"rules={len(fired)} out={len(cleaned)}")
    for name, unit in CMD_SHAPES.items():
        for size in (4096, 10_000, 10_001, 200_000, 1_000_000):
            line = "x " + fill(unit, size - 2)
            start = time.monotonic()
            verdict = check_command(line)
            ok &= row("direct-grd", name, size, time.monotonic() - start, "denied" if verdict else "allowed")
    print(f"rules in the table: {len(RULES)}; limit {LIMIT}s; overall {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
