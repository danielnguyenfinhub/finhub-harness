"""Proof for OR-S5: scripts/ship_scan.py, the advisory scan of the packed plugin files.

Shipped files are read from the zips themselves, each one is scanned or skipped with a reason, and
a file nobody accounted for makes coverage incomplete. A finding is a question and never fails the
build. Behaviour adapted from references/openrig/scripts/portability-report.mjs:25-52 (Apache-2.0);
the shipped-versus-scanned equality from references/openrig/scripts/check-substance-gate.mjs:52-65
(Apache-2.0). Each assertion message is the signature of one pre-registered mutant.
"""

# adapted from references/openrig/scripts/portability-report.mjs:25-52 (Apache-2.0)
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import time
import warnings
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/ship_scan.py"
PACKAGER = REPO / "scripts/package-plugin.sh"
TOKEN = "ghp_" + "a" * 36  # built in two parts so this file holds no secret shape
MAIL = "jdoe@corp.com.au"


def load(path: Path = SCRIPT) -> ModuleType:
    """Import the script fresh without bytecode, so a mutant is never stale."""
    name = f"ship_scan_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # a dataclass looks its own module up by name
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


def make_zip(path: Path, entries: list[tuple[str, str | bytes]]) -> Path:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # duplicate names warn on write
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in entries:
                zf.writestr(name, data)
    return path


def run(mod: ModuleType, capsys: pytest.CaptureFixture[str], *args: object) -> tuple[int, str]:
    capsys.readouterr()
    code = mod.main([str(a) for a in args])
    return code, capsys.readouterr().out


def cats(found: list[tuple[int, str, str]], category: str) -> list[tuple[int, str, str]]:
    return [f for f in found if f[1] == category]


def test_clean_zip_reports_complete_and_not_a_clean_bill(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    z = make_zip(tmp_path / "c.zip", [(f"f{i}.md", "hello\nworld\n") for i in range(3)])
    code, out = run(load(), capsys, z)
    assert "scanned 3 of 3" in out
    assert "FINDINGS: 0" in out
    assert "COVERAGE: COMPLETE" in out
    assert "not a clean bill" in out
    assert code == 0


def test_home_paths_are_reported() -> None:
    text = "x\ny\n/home/jdoe/proj/x\n/Users/jdoe/x\nC:\\Users\\jdoe\\x\n"
    found = cats(load().scan_text(text), "home-path")
    assert [f[0] for f in found] == [3, 4, 5]


def test_placeholder_home_paths_are_not_findings() -> None:
    text = "/home/user/proj\n/Users/you/x\nC:\\Users\\username\\x\n"
    found = cats(load().scan_text(text), "home-path")
    assert found == [], "placeholder home paths must not be reported"


def test_network_addresses_are_reported() -> None:
    text = "10.1.2.3\nhost.corp.internal\na.local\nb.lan\nc.ts.net\nd.home.arpa\n"
    found = cats(load().scan_text(text), "network-address")
    assert [f[0] for f in found] == [1, 2, 3, 4, 5, 6]


def test_reserved_addresses_are_not_findings() -> None:
    text = "127.0.0.1\n0.0.0.0\n255.255.255.0\n192.0.2.7\n198.51.100.4\n203.0.113.9\nv1.2.3\n"
    found = cats(load().scan_text(text), "network-address")
    assert found == [], "reserved addresses must not be reported"


def test_machine_paths_are_reported() -> None:
    mod = load()
    found = cats(
        mod.scan_text("/tmp/claude-0/x\n/var/folders/ab/c\n/private/tmp/d\n"), "machine-path"
    )
    assert len(found) == 3, "machine paths must be reported"
    assert cats(mod.scan_text("/tmp/build\n/tmp/foo\n"), "machine-path") == []


def test_emails_are_reported_and_noreply_and_examples_are_not() -> None:
    mod = load()
    assert len(cats(mod.scan_text(MAIL), "email")) == 1
    quiet = "noreply@corp.com\na@example.com\na@test.org\na@localhost\n"
    assert cats(mod.scan_text(quiet), "email") == []


def test_fork_urls_other_than_own_repo_are_reported() -> None:
    mod = load()
    two = "danielnguyenfinhub/OpenHarness\ndanielnguyenfinhub/finhub-harness-foo\n"
    assert len(cats(mod.scan_text(two), "fork-url")) == 2
    own = "danielnguyenfinhub/finhub-harness\ngithub.com/danielnguyenfinhub\n"
    assert cats(mod.scan_text(own), "fork-url") == []


def test_credential_value_is_never_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    z = make_zip(tmp_path / "a.zip", [("a.md", f"hello\ntoken {TOKEN} contact {MAIL}\n")])
    mod = load()
    for extra in ((), ("--locations-only",)):
        code, out = run(mod, capsys, *extra, z)
        assert TOKEN not in out, "a credential value must never reach the output"
        assert MAIL not in out, "a credential value must never reach the output"
        assert "a.md:2" in out
        assert code == 0
    _, out = run(mod, capsys, z)
    assert "github-token" in out


def test_private_key_block_is_one_credential_finding() -> None:
    body = "A" * 40
    text = f"a\nb\nc\n-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----\n"
    found = cats(load().scan_text(text), "credential")
    assert [f[0] for f in found] == [4]


def test_entry_in_a_new_top_level_directory_is_scanned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    z = make_zip(
        tmp_path / "n.zip", [("newdir/notes.md", "a\n/home/jdoe/x\n"), ("other.md", "fine\n")]
    )
    _, out = run(load(), capsys, z)
    assert "COVERAGE: COMPLETE" in out, "a file outside the known roots must be scanned"
    assert "scanned 2 of 2" in out
    assert "newdir/notes.md:2" in out


def test_binary_and_oversize_entries_are_skipped_and_accounted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = load()
    monkeypatch.setattr(mod, "MAX_BYTES", 100)
    z = make_zip(
        tmp_path / "s.zip",
        [("bin.dat", b"ab\x00cd"), ("big.txt", "x" * 500), ("ok.md", "fine\n")],
    )
    code, out = run(mod, capsys, z)
    assert "COVERAGE: COMPLETE" in out, "skipped entries must stay accounted for"
    assert "scanned 1 of 3" in out
    assert "bin.dat (binary)" in out
    assert "big.txt (oversize)" in out
    assert code == 0


def test_a_dropped_entry_makes_coverage_incomplete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = load()
    original = mod._scan_entry

    def lossy(zf: Any, info: Any) -> Any:
        if info.filename == "lost.md":
            return ("dropped", [])
        return original(zf, info)

    monkeypatch.setattr(mod, "_scan_entry", lossy)
    z = make_zip(tmp_path / "d.zip", [("lost.md", "x\n"), ("kept.md", "y\n")])
    code, out = run(mod, capsys, z)
    assert "COVERAGE: INCOMPLETE" in out, "a shipped file nobody scanned must be reported"
    assert "lost.md" in out.split("COVERAGE: INCOMPLETE", 1)[1]
    assert code == 3


def test_duplicate_entry_names_are_both_counted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    z = make_zip(tmp_path / "dup.zip", [("a.md", "one\n"), ("a.md", "two\n")])
    _, out = run(load(), capsys, z)
    assert "scanned 2 of 2" in out
    assert "COVERAGE: COMPLETE" in out


def test_locations_only_omits_matched_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    z = make_zip(tmp_path / "l.zip", [("a.md", "x\ny\n/home/jdoe/proj\n")])
    _, out = run(load(), capsys, "--locations-only", z)
    assert "a.md:3" in out
    assert "home-path" in out
    assert "jdoe" not in out


def test_findings_do_not_change_the_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    z = make_zip(tmp_path / "f.zip", [("a.md", "/home/jdoe/x\n10.1.2.3\n")])
    code, out = run(load(), capsys, z)
    assert code == 0, "findings must not change the exit code"
    assert "FINDINGS: 2 location(s)" in out


def test_operational_errors_exit_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = load()
    notzip = tmp_path / "t.zip"
    notzip.write_text("plain text", encoding="utf8")
    assert run(mod, capsys, tmp_path / "missing.zip")[0] == 2
    assert run(mod, capsys, notzip)[0] == 2
    assert run(mod, capsys)[0] == 2


def test_packager_stays_green_when_the_scan_exits_nonzero(tmp_path: Path) -> None:
    for name in (".claude-plugin", "skills"):
        shutil.copytree(
            REPO / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
    for name in ("LICENSE", "NOTICE", "README.md"):
        if (REPO / name).exists():
            shutil.copy(REPO / name, tmp_path / name)
    (tmp_path / "scripts").mkdir()
    shutil.copy(PACKAGER, tmp_path / "scripts/package-plugin.sh")
    (tmp_path / "scripts/ship_scan.py").write_text("import sys\nsys.exit(3)\n", encoding="utf8")
    proc = subprocess.run(
        ["bash", "scripts/package-plugin.sh"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, "the ship scan must not fail the build"
    assert "ship scan: exit 3" in proc.stderr
    for z in (
        "finhub-harness.plugin",
        "finhub-harness-skill.zip",
        "finhub-harness-evolve-skill.zip",
    ):
        assert (tmp_path / "dist" / z).is_file()


def test_real_packager_calls_the_scan_once_and_never_fails_on_it() -> None:
    text = PACKAGER.read_text(encoding="utf8")
    lines = [
        ln for ln in text.splitlines() if "ship_scan.py" in ln and not ln.lstrip().startswith("#")
    ]
    assert len(lines) == 1
    for z in ("dist/finhub-harness.plugin", "dist/finhub-harness-skill.zip"):
        assert z in lines[0]
    assert "dist/finhub-harness-evolve-skill.zip" in lines[0]
    assert "fail=1" not in text.split(lines[0], 1)[1]


def test_same_file_in_two_zips_is_one_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "a\nb\n/home/jdoe/x\nd\n"
    z1 = make_zip(tmp_path / "z1.zip", [("skills/p/a.md", body)])
    z2 = make_zip(tmp_path / "z2.zip", [("p/a.md", body + "/home/jdoe/y\n")])
    _, out = run(load(), capsys, z1, z2)
    assert (
        "FINDINGS: 2 location(s)" in out
    ), "the same file under two zip prefixes must be one location"
    assert out.count("a.md:3") == 1
    line3 = next(ln for ln in out.splitlines() if "a.md:3" in ln)
    assert "z1.zip" in line3 and "z2.zip" in line3
    line5 = next(ln for ln in out.splitlines() if "a.md:5" in ln)
    assert "z2.zip" in line5 and "z1.zip" not in line5


def test_dotted_quad_followed_by_a_dot_is_not_an_address() -> None:
    mod = load()
    for text in ("10.1.2.3.\n", "1.2.3.4.5\n"):
        found = cats(mod.scan_text(text), "network-address")
        assert found == [], f"an address followed by a dot must not be reported: {text!r}"
    for text in ("10.1.2.3 end\n", "see 10.1.2.3\n"):
        assert len(cats(mod.scan_text(text), "network-address")) == 1, text


@pytest.mark.parametrize(
    ("desc", "ok"),
    [("x" * 500, True), ("x" * 501, False), (None, False)],
    ids=["500-ok", "501-refused", "missing-refused"],
)
def test_packager_enforces_the_manifest_description_limit(
    tmp_path: Path, desc: str | None, ok: bool
) -> None:
    import json

    for name in (".claude-plugin", "skills"):
        shutil.copytree(
            REPO / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
    for name in ("LICENSE", "NOTICE", "README.md"):
        if (REPO / name).exists():
            shutil.copy(REPO / name, tmp_path / name)
    (tmp_path / "scripts").mkdir()
    shutil.copy(PACKAGER, tmp_path / "scripts/package-plugin.sh")
    (tmp_path / "scripts/ship_scan.py").write_text("import sys\nsys.exit(0)\n", encoding="utf8")
    manifest = tmp_path / ".claude-plugin/plugin.json"
    data = json.loads(manifest.read_text(encoding="utf8"))
    if desc is None:
        del data["description"]
    else:
        data["description"] = desc
    manifest.write_text(json.dumps(data), encoding="utf8")
    proc = subprocess.run(
        ["bash", "scripts/package-plugin.sh"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (proc.returncode == 0) == ok, "over-limit or missing description must be refused"
    assert (tmp_path / "dist").exists() == ok, "nothing may be packaged on a refused manifest"
    if not ok:
        assert "description" in proc.stderr, "the FAIL message must name the description"
