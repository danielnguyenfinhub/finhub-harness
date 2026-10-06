"""ere_tests.py <SKILL.md>: runs the ACTUAL shipped pattern with the shipped flags (grep -niE) on positive, boundary and
false-positive lines. Exit 0 if every positive hits and every negative stays silent."""
import subprocess, sys
from pathlib import Path
here = Path(__file__).resolve().parent
pat = subprocess.run(["bash", str(here / "ere.sh"), sys.argv[1]], capture_output=True, text=True).stdout.strip("\n")
a = lambda n: "a" * n
pos = {
 "sk 16": "sk-" + a(16), "sk mixed": "key: sk-FAKE-7q3zT9wXk2LmN8vB4cR6yH1d-EXAMPLE",
 **{f"gh{l} 20": f"gh{l}_" + a(20) for l in "pousr"},
 "AKIA 16": "AKIA" + "A" * 16,
 **{f"xox{l} 10": f"xox{l}-" + a(10) for l in "abprs"},
 "bearer 16": "Authorization: Bearer " + a(16), "BEARER caps": "BEARER " + a(16),
 "pem rsa": "-----BEGIN RSA PRIVATE KEY-----", "pem plain": "-----BEGIN PRIVATE KEY-----",
 "jwt 8.8": "eyJ" + a(8) + "." + a(8) + ".x", "jwt min": "t=eyJ" + a(8) + "." + a(8) + ".",
 **{f"kv {k}=": f"{k}=" + a(12) for k in ("api_key", "api-key", "apikey", "secret", "token", "password", "PASSWORD", "Token")},
 "kv colon": "token: " + a(12), "kv json": '"password": "' + a(12) + '"', "kv spaces": "secret = " + a(12),
 "kv dots": "token=" + "ab.cd.ef.gh.ij", "url": "https://user:pw@host.example/x", "url ftp": "ftp://u:p@h",
}
pos.update({
 "PM4 github_pat with underscore": "github_pat_ab_cdefghijklmnopqrstuvw", "PM16 sk- with underscore": "sk-ab_cdefghijklmnopqrstuvw",
 "github_pat 20": "github_pat_" + a(20), "sk_live 16": "sk_live_" + a(16), "sk_test 16": "sk_test_" + a(16), "AIza 35": "AIza" + a(35),
 "basic 20": "Authorization: Basic " + a(20), "basic b64": "Authorization: Basic dXNlcjpwYXNzd29yZDEyMzQ1Ng==",
 "secret_key": "secret_key=" + a(12), "secret-key colon": "secret-key: " + a(12), "aws_secret_access_key": "aws_secret_access_key=" + a(12),
 "access_key": "secret_access_key = " + a(12), "pw symbols": "password=P@ssw0rd!2024xx",
 **{f"bearer class {c}": "Bearer " + c * 16 for c in "._~+/=-"},
 **{f"kv value class {c}": "token=" + c * 12 for c in "/+_.@!#$%^&*-"},
 "jwt class -": "eyJ" + "-" * 8 + "." + "-" * 8 + ".", "jwt class _": "eyJ" + "_" * 8 + "." + "_" * 8 + ".",
 "documented false positive: env ref": "api_key=${API_KEY_FROM_ENVIRONMENT}", "documented false positive: kebab name": "secret: this-is-a-long-descriptive-name", "pre-gap 3": 'token"  =' + a(12), "post-gap 3": "token: \"'" + a(12),
})
neg = {
 "sk 15": "sk-" + a(15), "ghp 19": "ghp_" + a(19), "ghx": "ghx_" + a(20), "AKIA 15": "AKIA" + "A" * 15, "AKIB": "AKIB" + "A" * 16,
 "xoxb 9": "xoxb-" + a(9), "xoxz": "xoxz-" + a(10), "bearer 15": "Bearer " + a(15), "bearer word": "Bearer token",
 "jwt 7.8": "eyJ" + a(7) + "." + a(8) + ".x", "jwt 8.7": "eyJ" + a(8) + "." + a(7) + ".x", "jwt no dot": "eyJ" + a(30),
 "kv 11": "token=" + a(11), "kv xxxx": "token=xxxx", "kv angle": "password: <PASSWORD>", "kv word": "the token expired yesterday",
 "max_tokens": "max_tokens: 4096", "secret sauce": "secret sauce recipe: use more butter", "tokens plural": "tokens=" + a(20),
 "ask-": "task-force-alpha-bravo-charlie", "Xsk-": "Xsk-" + a(20), "Xghp": "Xghp_" + a(20), "Xxox": "Xxoxb-" + a(12), "Xeyj": "Xeyj" + a(8) + "." + a(8) + ".",
 "github_pat 19": "github_pat_" + a(19), "sk_live 15": "sk_live_" + a(15), "sk_prod": "sk_prod_" + a(16), "AIza 34": "AIza" + a(34), "basic 19": "Basic " + a(19),
 "basic prose": "a basic understanding of the framework is required", "jwt no trailing dot": "eyJ" + a(8) + "." + a(8),
 "post-gap 4": "token:    " + a(12), "pre-gap 4": 'token"   =' + a(12), "sk_ word": "task_live_" + a(16),
 "documented miss: bearer two spaces": "Bearer  " + a(16), "documented miss: short password": "password=Summer2024!", "documented miss: twilio": "AC" + "0" * 32,
 "XAIza": "XAIza" + a(35), "Xgithub_pat": "Xgithub_pat_" + a(20), "Xbasic": "Xbasic " + a(20), "sha": "commit 3f786850e387550fdab836ed7e6dc881de23001b", "uuid": "123e4567-e89b-12d3-a456-426614174000",
 "host:port": "http://host:8080/path@x", "path:line": "See README.md:12 for details", "url no cred": "https://example.com/a/b",
 "private word": "a PRIVATE KEY is mentioned here", "begin only": "-----BEGIN CERTIFICATE-----", "begin public": "-----BEGIN PUBLIC KEY-----", "url empty user": "https://:pw@host", "begin 4": "----BEGIN PRIVATE KEY----",
}
bad = []
def hit(s):
    return subprocess.run(["grep", "-niE", pat], input=s + "\n", capture_output=True, text=True).returncode == 0
for k, s in pos.items():
    if not hit(s): bad.append("MISS " + k)
for k, s in neg.items():
    if hit(s): bad.append("FALSE-HIT " + k)
print(f"positives {len(pos)}, negatives {len(neg)}; " + ("ere ok" if not bad else "; ".join(bad)))
sys.exit(1 if bad else 0)
