"""The judge's 50 independent mutants I01-I50 (from the round-1 verdict, j9/indep.py), parametrised.
Usage: J_TREE=<patched tree> J_SCRATCH=<dir> J_PY=<python> [J_DRY=1] python 02_strategy-architect_C9_judge_mutants.py [ids]
I28 is re-expressed against the rev-2 text (marked). Each mutation must occur exactly once.
"""
import os,sys,shutil,subprocess,tempfile,difflib,json
from concurrent.futures import ThreadPoolExecutor
PAT=os.path.abspath(os.environ['J_TREE']); PY=os.environ.get('J_PY','python'); SCR=os.path.abspath(os.environ['J_SCRATCH'])
G='src/master_finhub/evals/gates.py'; S='src/master_finhub/sandbox/stream.py'
M=[
('I01','no strip of the command string',G,'    text = raw.strip()\n','    text = raw\n'),
('I02','length cap >= instead of >',G,'    if len(text) > MAX_TEXT_CHARS:\n        return "command is too long"\n    if any(ch in SHELL','    if len(text) >= MAX_TEXT_CHARS:\n        return "command is too long"\n    if any(ch in SHELL'),
('I03','metachar scan only on first char',G,'any(ch in SHELL_METACHARS for ch in text)','any(ch in SHELL_METACHARS for ch in text[:1])'),
('I04','metachar scan only outside quotes (strip quoted bits)',G,'any(ch in SHELL_METACHARS for ch in text)','any(ch in SHELL_METACHARS for ch in __import__("re").sub(r"\'[^\']*\'|\\"[^\\"]*\\"","",text))'),
('I05','shlex comments=True',G,'shlex.split(text)','shlex.split(text, comments=True)'),
('I06','shlex posix=False',G,'shlex.split(text)','shlex.split(text, posix=False)'),
('I07','executable dash check only --',G,'argv[0].startswith("-")','argv[0].startswith("--")'),
('I08','executable = check only trailing',G,'"=" in argv[0]','argv[0].endswith("=")'),
('I09','NUL checked only in argv[0]',G,'any("\\x00" in a for a in argv)','"\\x00" in argv[0]'),
('I10','encodability checked only argv[0]',G,'        for a in argv:\n            a.encode("utf-8")','        for a in argv[:1]:\n            a.encode("utf-8")'),
('I11','item length checked only argv[0]',G,'any(len(a) > MAX_TEXT_CHARS for a in argv)','len(argv[0]) > MAX_TEXT_CHARS'),
('I12','cwd existence instead of is_dir',G,'if not cwd.is_dir():','if not cwd.exists():'),
('I13','guard sees only the executable',G,'line = shlex.join(argv)','line = argv[0]'),
('I14','guard cwd is the raw unresolved cwd',G,'"cwd": str(cwd)}','"cwd": gate.cwd}'),
('I15','pass counted for not-run',G,'passed = sum(r.status == "pass" for r in results)','passed = sum(r.status in ("pass", "not-run") for r in results)'),
('I16','ok without non-empty check',G,'total > 0 and passed == total','passed == total'),
('I17','spawn uses unresolved gate cwd',G,'cwd=str(plan.cwd)','cwd=gate.cwd'),
('I18','--root ignored',G,'Workspace(args.root if args.root is not None else os.getcwd())','Workspace(os.getcwd())'),
('I19','check_write instead of check_read',G,'ws.check_read(gate.cwd)','ws.check_write(gate.cwd)'),
('I20','shell path via PATH lookup',G,'SHELL_PATH: Final = "/bin/sh"','SHELL_PATH: Final = "sh"'),
('I21','FIFO check exists instead of isfile',G,'if not os.path.isfile(path):','if not os.path.exists(path):'),
('I22','BOM accepted',G,'raw.decode("utf-8")','raw.decode("utf-8-sig")'),
('I23','RecursionError not caught at load',G,'except (ValueError, RecursionError):','except ValueError:'),
('I24','schema_version bool/float accepted',G,'if type(version) is not int or version != SCHEMA_VERSION:','if version != SCHEMA_VERSION:'),
('I25','empty gates accepted at load',G,'if not isinstance(rows, list) or not rows:','if not isinstance(rows, list):'),
('I26','total budget boundary < instead of <=',G,'if remaining <= 0:','if remaining < 0:'),
('I27','total_s param ignored',G,'deadline = time.monotonic() + total_s','deadline = time.monotonic() + MAX_TOTAL_S'),
('I28','SIGTERM handler not restored (re-expressed for rev 2)',G,'            signal.signal(old_sig, signal.SIG_DFL if previous is None else previous)\n','            pass\n'),
('I29','redaction skipped on stderr only',G,'    err, cut_err = _tail(res.stderr)','    err, cut_err = res.stderr[-TAIL_CHARS:], False'),
('I30','cut flag drops capture truncation',G,'cut = res.truncated or cut_out or cut_err','cut = cut_out or cut_err'),
('I31','tail takes the head',G,'return cleaned[-TAIL_CHARS:],','return cleaned[:TAIL_CHARS],'),
('I32','signal death reported as pass',G,'    if res.exit_code == 0:\n        return done("pass"','    if res.exit_code == 0 or res.exit_code < 0:\n        return done("pass"'),
('I33','timeout check after exit code',G,'    if res.timed_out:\n        return done("timeout", None, f"timed out after {timeout_s:g}s", out, err, cut)\n    if res.exit_code is None:','    if res.exit_code is None and res.timed_out:\n        return done("timeout", None, f"timed out after {timeout_s:g}s", out, err, cut)\n    if res.exit_code is None:'),
('I34','policy error exit when only some refused -> 1 if any fail',G,'return 2 if any(r.status == "policy-error" for r in report.gates) else 1','return 2 if all(r.status == "policy-error" for r in report.gates) else 1'),
('I35','shell gate guard line is the argv join',G,'            line = raw\n','            line = shlex.join(argv)\n'),
('I36','shell: refused-without-flag check removed order (allow_shell ignored when argv nonblank)',G,'            if not allow_shell:\n                return "shell gate refused: pass --allow-shell"\n','            pass\n'),
('I37','plan crash not fail-closed (re-raise)',G,'    except Exception:  # noqa: BLE001 - fail closed: an unexpected error is a refusal\n        return "policy check failed"','    except ZeroDivisionError:\n        return "policy check failed"'),
('I38','duplicate JSON keys last-wins',G,'    if len(out) != len(pairs):\n        raise ValueError("duplicate JSON key")\n','    pass\n'),
('I39','unknown gate keys tolerated',G,'    if not set(entry) <= GATE_KEYS:\n        raise _bad(f"gate {n} has an unknown key")\n','    pass\n'),
('I40','id charset: leading dash allowed',G,'and value[0].isalnum()\n','and True\n'),
('I41','timeout bool accepted',G,'if isinstance(value, bool) or not isinstance(value, (int, float)):','if not isinstance(value, (int, float)):'),
('I42','timeout lower bound >= 0',G,'return seconds if 0 < seconds <= MAX_TIMEOUT_S','return seconds if 0 <= seconds <= MAX_TIMEOUT_S'),
('I43','argv list items need not be strings',G,'all(isinstance(a, str) for a in argv)','True'),
('I44','stream: stdout tail cap 64000 -> unbounded',S,'DEFAULT_MAX_OUTPUT_BYTES: Final = 64_000','DEFAULT_MAX_OUTPUT_BYTES: Final = 64_000_000'),
('I45','exit chunk emitted even if proc not finished (rc None) -> str(None)',S,'            if rc is not None:\n                finished = True','            if True:\n                finished = True'),
('I46','stream: finally does not killpg',S,'    finally:\n        stop.set()\n        _kill_group(proc)\n','    finally:\n        stop.set()\n'),
('I47','env scrub extra keys',S,'SENSITIVE_ENV: Final = re.compile(r"KEY|PASSWORD|SECRET|TOKEN", re.IGNORECASE)','SENSITIVE_ENV: Final = re.compile(r"KEY|PASSWORD|SECRET", re.IGNORECASE)'),
('I48','Gate dataclass default shell: command argv path ignores nonlist',G,'            argv = parsed or ()\n','            argv = tuple(parsed) if parsed else ()\n'),
('I49','report counts failed wrong',G,'return GateReport(tuple(results), passed, total - passed, total,','return GateReport(tuple(results), passed, total - passed - 1, total,'),
('I50','not-run message status policy-error for others',G,'_skipped(g.id, "not-run", "another gate was refused")','_skipped(g.id, "policy-error", "another gate was refused")'),
]
def run(m):
    i,what,f,old,new=m
    src=open(os.path.join(PAT,f),encoding='utf-8').read()
    n=src.count(old)
    if n!=1: return (i,what,'BADMUT count=%d'%n,'')
    if os.environ.get('J_DRY'): return (i,what,'DRY','')
    d=tempfile.mkdtemp(prefix='ind_',dir=SCR)
    t=os.path.join(d,'t')
    shutil.copytree(PAT,t,symlinks=True,ignore=shutil.ignore_patterns('.git','__pycache__','dist','references'))
    open(os.path.join(t,f),'w',encoding='utf-8').write(src.replace(old,new))
    assert open(os.path.join(t,f),encoding='utf-8').read()!=src
    env=dict(os.environ); env.pop('PYTHONPATH',None)
    try:
        r=subprocess.run([PY,'-B','-m','pytest','-x','-q','-p','no:cacheprovider','tests/test_gates.py'],cwd=t,env=env,capture_output=True,text=True,timeout=300)
    except subprocess.TimeoutExpired:
        return (i,what,'KILLED(timeout)','')
    last=r.stdout.strip().splitlines()
    fl=[l for l in last if l.startswith('FAILED')]
    st='SURVIVED' if r.returncode==0 else 'KILLED'
    shutil.rmtree(d,ignore_errors=True)
    return (i,what,st,(fl[0][:150] if fl else (last[-1] if last else '')))
if __name__=='__main__':
    only=sys.argv[1:] 
    ms=[m for m in M if not only or m[0] in only]
    with ThreadPoolExecutor(4) as ex: res=list(ex.map(run,ms))
    for r in res: print(*r,sep=' | ')
    print('TOTAL',len(res),'killed',sum(r[2].startswith('KILLED') for r in res),'survived',[r[0] for r in res if r[2]=='SURVIVED'],'bad',[r[0] for r in res if r[2].startswith('BAD')])
