"""C9 probe matrix: the resolution-mismatch family between the RUNNER process and the CHILD for the
executable word of a non-shell gate. Real CLI, real children, marker files. Usage:

    J_TREE=<patched tree> J_SCRATCH=<dir> J_PY=<python> python 02_strategy-architect_C9_probe_matrix.py [--strace]

The table of rows lives once, in tests/gate_matrix.py of the tree (it is also what
tests/test_gates.py runs). Each row builds a fresh folder holding a test-made "shell" (an executable
file called bash that creates MARK in its cwd with a shell builtin), the row's links and one gate, and
runs the REAL CLI three ways: M1 runner cwd = B/a/b (not the gate's), --root B; M2 runner cwd = the
gate's cwd; M3 runner cwd = B/a/b, --root B/sub (root elsewhere, default gate cwd). Verdicts:
REFUSED (every run: exit 2, policy-error, no MARK), BYPASS (a MARK although the row expects a
refusal), LIMIT (a documented limit: MARK expected, with the reason), ANOMALY (anything else).
With --strace, `strace -f -e trace=execve` also counts exec calls of the gate's executable.
Exit 1 if any row is a BYPASS or an ANOMALY.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

TREE = Path(os.environ["J_TREE"]).resolve()
SCR = Path(os.environ["J_SCRATCH"]).resolve()
PY = os.environ.get("J_PY", sys.executable)
STRACE = "--strace" in sys.argv

spec = importlib.util.spec_from_file_location("gate_matrix", TREE / "tests" / "gate_matrix.py")
assert spec is not None and spec.loader is not None
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)


def main() -> int:
    SCR.mkdir(parents=True, exist_ok=True)
    counts = {"REFUSED": 0, "LIMIT": 0, "BYPASS": 0, "ANOMALY": 0}
    print(f"{'row':5} {'description':62} {'M1 other':9} {'M2 same':9} {'M3 root=sub':11} verdict")
    for row in gm.ROWS:
        rid, desc, _files, _gate, _path, extra = row
        res = [gm.run_row(row, m, TREE / "src", PY, SCR, STRACE) for m in ("M1", "M2", "M3")]
        cells = [r[0] for r in res]
        used = [c for c in cells if c != "n/a"]
        if "limit" in extra:
            ok = all(c == "MARK" for c in used)
            verdict = "LIMIT: " + extra["limit"] if ok else "ANOMALY (limit row did not run)"
            counts["LIMIT" if ok else "ANOMALY"] += 1
        elif all(c == "refused" for c in used):
            verdict = "REFUSED"
            counts["REFUSED"] += 1
        elif any(c == "MARK" for c in used):
            verdict = "BYPASS"
            counts["BYPASS"] += 1
        else:
            verdict = "ANOMALY " + " ".join(r[1] for r in res)
            counts["ANOMALY"] += 1
        notes = ""
        if STRACE:
            notes = "  [gate execs " + "/".join(r[1].split("gate-execs=")[-1] if "gate-execs=" in r[1] else "-" for r in res) + "]"
        print(f"{rid:5} {desc[:62]:62} {cells[0]:9} {cells[1]:9} {cells[2]:11} {verdict}{notes}", flush=True)
    print("SUMMARY", counts, "rows", len(gm.ROWS))
    return 1 if counts["BYPASS"] or counts["ANOMALY"] else 0


if __name__ == "__main__":
    sys.exit(main())
