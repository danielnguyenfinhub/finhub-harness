"""Audit leads 4 and 5: wildcards, braces, ANSI-C strings, variables, bare-word symlinks, cd,
extra credential paths and rm of paths under system directories. The guard stays a tripwire."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from master_finhub.tools.safety import check_command
from master_finhub.tools.sensitive_paths import is_sensitive_path


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home"
    (h / ".aws").mkdir(parents=True)
    (h / ".aws" / "credentials").write_text("x")
    (h / ".ssh").mkdir()
    (h / ".ssh" / "config").write_text("x")
    (h / "projects").mkdir()
    (h / "notes.txt").write_text("ok")
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.chdir(h)
    return h


def denied(cmd: str) -> bool:
    return check_command(cmd) is not None


WILDCARD = [
    "cat ~/.ss?/config",
    "cat ~/.s[s]h/config",
    "cat ~/.{ssh,x}/config",
    "cat ~/.aw*/credentials",
    "cat $'/root/.s\\x73h/config'",
    "d=.aws; cat ~/$d/credentials",
    "cat ~/.config/gclou?/x",
    "cat ~/.{a,b,{aws,c}}/credentials",
    "cat $'~/.aws/credentials'",
    "export d=.aws && cat ~/${d}/credentials",
    'bash -c "cat ~/.aw?/credentials"',
]


@pytest.mark.parametrize("cmd", WILDCARD)
def test_wildcard_forms_denied(cmd: str) -> None:
    assert denied(cmd)


BENIGN = [
    "cat README.md",
    "ls ~/projects",
    "echo hello",
    "cat ./notes.txt",
    "cat notes.txt",
    "ls *",
    "ls .*",
    "cat src/*.py",
    "ls ~/proj?cts",
    "echo {a,b}",
    "[ -f x ] && echo $'a\\nb'",
    "d=projects; ls ~/$d",
    "cd projects && ls",
    "rm -rf ~/projects/build",
    "rm -rf /home/user/projects",
    "ls .envrc-notes",
]


@pytest.mark.parametrize("cmd", BENIGN)
def test_benign_neighbours_allowed(cmd: str) -> None:
    assert not denied(cmd)


def test_bare_word_symlink_to_credential_denied(home: Path) -> None:
    os.symlink(home / ".aws" / "credentials", home / "creds")
    assert denied("cat creds")
    assert denied("cat ./creds")


def test_bare_word_normal_file_allowed(home: Path) -> None:
    assert not denied("cat notes.txt")


def test_cd_then_relative_credential_denied(home: Path, tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()
    os.chdir(other)
    assert denied(f"cd {home}/.ssh && cat config")
    assert denied(f"cd {home}/.ssh; cat config")
    assert denied("cd ~/.ssh; cat id_rsa")


def test_cd_then_bare_symlink_denied(home: Path, tmp_path: Path) -> None:
    box = tmp_path / "box"
    box.mkdir()
    os.symlink(home / ".aws" / "credentials", box / "link")
    os.chdir(tmp_path)
    assert denied(f"cd {box} && cat link")
    assert not denied(f"cd {box} && cat nothing")


def test_cd_unknown_target_keeps_relative_checks(home: Path) -> None:
    os.symlink(home / ".aws" / "credentials", home / "creds")
    assert denied("cd $UNSET_DIR_X; cat creds")


@pytest.mark.parametrize(
    "path",
    [
        "~/.config/gh/hosts.yml",
        "~/.cargo/credentials",
        "~/.cargo/credentials.toml",
        "~/.config/anthropic/key",
        "~/.config/anthropic",
        "project/.env",
        ".env",
        "app/.env.production",
        "/proc/self/environ",
        "/proc/1234/environ",
    ],
)
def test_new_credential_paths(path: str) -> None:
    assert is_sensitive_path(path, resolve=False)
    assert denied(f"cat {path}")


@pytest.mark.parametrize(
    "path", ["~/.config/gh/config.yml", "~/.cargo/bin/x", "/proc/cpuinfo", "env.md"]
)
def test_new_paths_neighbours_allowed(path: str) -> None:
    assert not is_sensitive_path(path, resolve=False)


@pytest.mark.parametrize(
    "cmd",
    [
        "rm -rf /home/bob",
        "rm -rf /usr/lib",
        "rm -rf /var/lib",
        "rm -rf /etc/ssh",
        "rm -rf /home/bob/",
        "rm -rf //home//bob",
        "rm -rf $HOME_LIKE",
        "cd /home/bob; rm -rf *",
    ],
)
def test_rm_under_system_dirs_denied(cmd: str) -> None:
    assert denied(cmd)


def test_rm_user_home_itself_denied(home: Path) -> None:
    assert denied(f"rm -rf {home}")
    assert denied(f"rm -rf {home}/")


def test_cp_into_home_subdir_still_allowed(home: Path) -> None:
    assert not denied(f"cp notes.txt {home}/projects")
    assert not denied("cp notes.txt /home/bob/x")


def test_brace_explosion_fails_closed() -> None:
    word = "".join("{a,b}" for _ in range(12))
    assert denied(f"echo {word}")


def test_new_scans_stay_bounded() -> None:
    cmds = [
        "echo " + "{a,b,c}" * 6,
        "echo " + "*?[a]" * 1500,
        "echo " + "$'\\x41' " * 1000,
        "echo " + "{" * 4000 + ",",
        "cd x; " * 1500 + "cat y",
        "d=a; " * 1500 + "cat $d",
    ]
    for c in cmds:
        t = time.process_time()
        check_command(c[:10_000])
        assert time.process_time() - t < 1.0, c[:30]


@pytest.mark.parametrize(
    "cmd",
    ["cat ~/.cargo/credential?", "cat ~/.config/gh/hosts.y*", "cat ~/.c[a]rgo/credentials.toml"],
)
def test_wildcard_new_credential_names_denied(cmd: str) -> None:
    assert denied(cmd)


def test_star_does_not_match_dotfiles() -> None:
    assert not denied("cat ~/*ssh/config")  # a shell star never matches a leading dot


def test_find_delete_under_system_dir_denied() -> None:
    assert denied("find /home/bob -delete")
