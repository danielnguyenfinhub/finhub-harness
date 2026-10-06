"""Independent ReDoS sweep: runs the ACTUAL shipped grep (GNU grep -niE with the pattern extracted from SKILL.md) on adversarial lines."""
import subprocess, sys, time
pat = subprocess.run(["bash", "../support/ere.sh", "skills/finhub-harness-evolve/SKILL.md"], capture_output=True, text=True).stdout.strip("\n")
assert pat.startswith("\\bsk-") and "\n" not in pat, pat[:40]
cases = {
  "sk-+a": lambda n: "sk-" + "a" * n,
  "sk-_repeat": lambda n: "sk-" * n,
  "task-repeat": lambda n: "task-aaaaaaaa" * (n // 13),
  "://a:": lambda n: "://" + "a:" * (n // 2),
  "://a_no_at": lambda n: "://" + "a" * n,
  "://x:y:x:y@miss": lambda n: "://" + "x:y" * (n // 3),
  "at-run": lambda n: "@" * n,
  "colon-run": lambda n: ":" * n,
  "token-space": lambda n: "token" + " " * n,
  "token=rep": lambda n: "token=" * (n // 6),
  "token=a15": lambda n: "token=" + "a" * 11 + ("token=" + "a" * 11) * (n // 17),
  "api_key-rep": lambda n: "api_key" * (n // 7),
  "bearer-sp": lambda n: "bearer" + " " * n,
  "bearer-sp-a": lambda n: "bearer " + " " * n + "a" * 15,
  "bearer-2sp-rep": lambda n: "bearer  " * (n // 8),
  "bearer-1sp-long-run": lambda n: "bearer " + "a" * n,
  "bearer-sp-rep-15": lambda n: ("bearer " + " " * 15) * (n // 22),
  "bearer-15": lambda n: ("bearer " + "a" * 15 + " ") * (n // 23),
  "eyJ-rep": lambda n: "eyJ" * (n // 3),
  "eyJ8.rep": lambda n: ("eyJ" + "a" * 8 + ".") * (n // 12),
  "BEGIN-A": lambda n: "-----BEGIN " + "A" * n,
  "BEGIN-rep": lambda n: "-----BEGIN A" * (n // 12),
  "AKIA-rep": lambda n: "AKIA" * (n // 4),
  "ghp_rep": lambda n: "ghp_" * (n // 4),
  "xox": lambda n: "xoxb-" * (n // 5),
  "github_pat-rep": lambda n: "github_pat_" * (n // 11),
  "sk_live-rep": lambda n: "sk_live_" * (n // 8),
  "sk_live-run": lambda n: "sk_live_" + "a" * n,
  "AIza-rep": lambda n: "AIza" * (n // 4),
  "AIza-run": lambda n: "AIza" + "a" * n,
  "basic-sp": lambda n: "basic" + " " * n,
  "basic-rep": lambda n: "basic " * (n // 6),
  "basic-run": lambda n: "basic " + "a" * n,
  "secret_access-rep": lambda n: "secret_access_" * (n // 14),
  "secret_key-rep": lambda n: "secret_key" * (n // 10),
  "token=sym-run": lambda n: "token=" + "!" * n,
  "password=@-rep": lambda n: "password=@" * (n // 10),
  "token-gap-rep": lambda n: 'token"  =   ' * (n // 12),
  "kv-11-rep": lambda n: ("password=" + "a" * 11 + " ") * (n // 20),
  "mixed": lambda n: ("sk-aaaa token=ab bearer x://a:b eyJ1 ") * (n // 40),
}
sizes = [4096, 200_000, 1_000_000]
worst = {}
for name, f in cases.items():
    row = []
    for n in sizes:
        data = f(n) + "\n"
        t = time.perf_counter()
        subprocess.run(["grep", "-niE", pat], input=data, capture_output=True, text=True, timeout=120)
        row.append(time.perf_counter() - t)
    worst[name] = row
    ratio = row[-1] / max(row[-2], 1e-6)  # 200k -> 1M is 5x the size; linear means about x5
    print(f"{name:16s} " + " ".join(f"{x:7.4f}" for x in row) + f"   5x size (200k to 1M) -> time x{ratio:4.1f}")
print("max seconds at 1,000,000 chars:", max(r[-1] for r in worst.values()))
