import sys, time
sys.path.insert(0, "skills/finhub-harness/scripts")
from lint_harness import LAZY_RE, SPAWN_RE
units = {
 "ws-run": lambda n: "based on" + " " * n + "x",
 "nl-run": lambda n: "as" + "\n" * n + "x",
 "repeat-prefix": lambda n: "based on " * n + "x",
 "repeat-prefix-the": lambda n: "based on the " * n + "x",
 "repeat-as": lambda n: "as we " * n + "x",
 "alt-near-miss": lambda n: "based on your findin " * n,
 "nbsp-run": lambda n: "as we" + " " * n + "x",
 "mixed": lambda n: ("as we based on your " * n),
}
for name, f in units.items():
    row = []
    for n in (25_000, 50_000, 100_000, 200_000):
        s = f(n)
        t0 = time.perf_counter(); list(LAZY_RE.finditer(s)); SPAWN_RE.search(s)
        row.append(f"{n}:{time.perf_counter()-t0:.4f}s")
    print(f"{name:18}", " ".join(row))
# the naive per-match count variant, for contrast
s = "based on the research\n" * 30000
t0 = time.perf_counter()
for m in LAZY_RE.finditer(s): s.count("\n", 0, m.start())
print("naive count from 0, 30000 matches:", f"{time.perf_counter()-t0:.3f}s")
