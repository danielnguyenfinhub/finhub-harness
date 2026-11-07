"""Re-audit of the command guard: unset variables and parameter operators, more directory
changes, wildcards against the real directory, hard links, credential wildcards, command
substitution and xargs. The guard stays a tripwire; pipe, stdin and interpreter-supplied paths
are not covered (see sensitive_paths.py)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from master_finhub.tools.safety import check_command, check_rule


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME with credentials; the cwd `work` holds aliases of them; `clean` holds none."""
    h = tmp_path / "home"
    for d in (".ssh", ".aws", ".config/gh", ".cargo", "projects"):
        (h / d).mkdir(parents=True)
    (h / ".ssh" / "id_rsa").write_text("k")
    (h / ".ssh" / "config").write_text("c")
    (h / ".aws" / "credentials").write_text("c")
    (h / ".config" / "gh" / "hosts.yml").write_text("t")
    w = tmp_path / "work"
    (w / "d" / "sub").mkdir(parents=True)
    (w / "e").mkdir()
    os.symlink(h / ".ssh" / "id_rsa", w / "d" / "f")
    os.symlink(h / ".ssh" / "id_rsa", w / "d" / "sub" / "g")
    os.symlink(h / ".ssh" / "id_rsa", w / "link")
    os.symlink(h / ".ssh", w / "k")
    os.link(h / ".ssh" / "id_rsa", w / "hard")
    (w / "plain.txt").write_text("x")
    os.link(w / "plain.txt", w / "plain2")  # two links, but not a credential
    y = tmp_path / "dyn"  # like `work` but without the link to a credential directory
    (y / "d" / "sub").mkdir(parents=True)
    os.symlink(h / ".ssh" / "id_rsa", y / "d" / "f")
    os.symlink(h / ".ssh" / "id_rsa", y / "d" / "sub" / "g")
    os.symlink(h / ".ssh" / "id_rsa", y / "link")
    (tmp_path / "clean").mkdir()
    for n in ("notes.md", "a1.md", "readme"):
        (tmp_path / "clean" / n).write_text("x")
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.chdir(w)
    return h


def denied(cmd: str) -> bool:
    return check_command(cmd) is not None


def in_dyn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path / "dyn")


def in_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path / "clean")


# --- 1. unset or unknown variables, parameter operators -------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "cat .e${x}nv",
        "cat d${unset}/f",
        "cat ${D}d/f",
        "cat d/${unset}f",
        "cat d/f$unset",
        "cat d/f${a}${b}",
    ],
)
def test_unset_variable_reads_as_empty(cmd: str) -> None:
    assert denied(cmd)


@pytest.mark.parametrize(
    "cmd",
    [
        "cat d/${F:-f}",
        "cat d/${F-f}",
        "cat d/${F:=f}",
        "cat ${D:+d}/f",
        "cat ${D+d}/f",
        "F=zz; cat d/${F:-f}",
        "D=d; cat ${D:-}/f",
        "D=d; F=f; cat ${D:-}/${F:-}",
        "D=d; F=f; cat $D/${F:-x}",
    ],
)
def test_parameter_operators_check_both_branches(cmd: str) -> None:
    assert denied(cmd)


@pytest.mark.parametrize(
    "cmd",
    [
        "echo ${X:-hello}",
        "echo $a$b$c$d$e$f$g$h",
        "cat plain${u}.txt",
        "cat ${P:-plain}.txt",
        "echo ${A:+yes} $B",
        "cat $UNSET",
    ],
)
def test_unset_variable_benign_allowed(cmd: str) -> None:
    assert not denied(cmd)


def test_variable_count_cap_refuses_instead_of_forgetting() -> None:
    many = "; ".join(f"v{i}=x" for i in range(70))
    assert check_rule(f"{many}; d=.aws; cat ~/$d/credentials") == "check-failed"
    assert check_rule(f"{many}; echo plain") is None  # a word without `$` is not refused


def test_many_unresolved_references_in_one_word_keep_the_all_empty_reading() -> None:
    assert denied("cat " + "${x}" * 40 + ".env")
    assert not denied("echo " + "${x}" * 40)


def test_long_substituted_word_refused() -> None:
    assert check_rule("D=" + "a" * 4000 + "; cat $D$D$D") is not None


# --- 2. directory changes ------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "pushd d; cat f",
        "pushd d && cat f",
        "pushd e; pushd ../d; cat f",
        "env -C d cat f",
        "env --chdir=d cat f",
        "env --chdir d cat f",
        "tar --directory=d -cf - f",
        "tar --directory d -cf - f",
        "tar -cf - -C d f",
        "tar -cf - -Cd f",
        "git -C d diff f",
        "make -C d f",
        'env -C "$(echo d)" cat f',
    ],
)
def test_directory_change_forms_tracked(cmd: str) -> None:
    assert denied(cmd)


def test_popd_restores_the_previous_directory() -> None:
    assert not denied("pushd d; popd; cat f")  # no `f` in the cwd
    assert denied("pushd e; popd; cat link")  # `link` is an alias in the cwd
    assert denied("cd d; pushd e; popd; cat f")  # back in d


def test_segment_directory_does_not_persist() -> None:
    assert not denied("env -C d true; cat f")
    assert not denied("tar -C d -cf x.tar sub; cat f")
    assert denied("env -C d true; cat link")


@pytest.mark.parametrize(
    "cmd",
    [
        'cd "$(echo d)"; cat f',
        "cd `echo d`; cat f",
        "cd $(echo d); cat f",
        "cd $UNSET_DIR; cat f",
        'pushd "$(echo d)"; cat f',
        'cd "$(echo d)"; cat sub/g',  # two levels below the last known directory
        'cd "$(echo d)"; cat link',  # and the last known directory itself
        'cd "$(echo d/sub)"; cat g',  # two levels below
    ],
)
def test_non_literal_directory_checks_every_listed_directory(
    cmd: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_dyn(tmp_path, monkeypatch)
    assert denied(cmd)
    assert not denied(cmd.rsplit("; ", 1)[0] + "; cat nothing")


def test_non_literal_segment_directory_checks_listed_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_dyn(tmp_path, monkeypatch)
    assert denied('env -C "$(echo d)" cat f')
    assert denied('tar -C "$(echo d)" -cf x.tar f')
    assert not denied('env -C "$(echo d)" cat nothing')


def test_non_literal_directory_benign_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_clean(tmp_path, monkeypatch)
    assert not denied('cd "$(echo e)"; cat notes.md')
    assert not denied('env -C "$(echo x)" cat readme')


def test_non_literal_directory_listing_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big = tmp_path / "big"
    for i in range(300):
        (big / f"s{i}" / "t").mkdir(parents=True)
    monkeypatch.chdir(big)
    t = time.process_time()
    assert not denied('cd "$(echo s1)"; cat nothing')
    assert time.process_time() - t < 2.0


# --- 3. wildcards against the real directory, hard links -----------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "cat l*",
        "cat l?nk",
        "cat [l]ink",
        "cat h*",
        "cat h[a]rd",
        "cat hard",
        "cat ./hard",
        "cat k/c*",
        "cat k*/config",
        "cd d; cat f*",
        "cd d; cat *",
        "cd d; cat ?",
        "cd d; cat [f]",
        "cat d/f*",
        "cat d/*/g",
    ],
)
def test_bare_glob_reaching_an_alias_denied(cmd: str) -> None:
    assert denied(cmd)


def test_hard_link_to_a_credential_denied_by_inode(home: Path) -> None:
    assert denied("cat hard")
    assert not denied("cat plain2")  # two links, but not a credential's inode
    assert not denied("cat plain.txt")


def test_bare_glob_benign_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    in_clean(tmp_path, monkeypatch)
    assert not denied("ls *")
    assert not denied("cat n*")
    assert not denied("cat [a-z]*")
    assert not denied("cat ./a[0-9]*.md")
    assert not denied("cp *.md /tmp/x")


def test_glob_listing_is_bounded_per_word_and_per_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big = tmp_path / "big"
    big.mkdir()
    for i in range(4200):
        (big / f"f{i}").write_text("")
    t = time.process_time()
    assert not denied("ls big/f1*")  # one word: read in part, still allowed
    assert time.process_time() - t < 2.0
    monkeypatch.chdir(tmp_path)
    words = " ".join(f"big/f{i}*" for i in range(30))
    assert check_rule(f"ls {words}") == "path-budget"


# --- 4. credential wildcards ----------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "cat ~/.config/gh/*",
        "cat ~/.cargo/*",
        "cat ~/.cargo/c*",
        "cat ~/.config/*/hosts.yml",
        "cat ~/.config/g?/hosts.yml",
        "cat ~/.config/*/x",
        "cat /proc/self/envi?on",
        "cat /proc/*/envi?on",
        "cat /proc/1/envi?on",
        "cat ~/.*/gcloud/x",
        "cat ~/.c*/g*/x",
        "cat ~/.c*/*/*",
        "cat ~/.*/*/*",
        "cat ~/.*/*",
        "cp -r ~/.??* /tmp/x",
        "tar c ~/.??*",
        "cp $HOME/.* /tmp/x",
        "cp ~/.s[[:alpha:]]h /tmp/x",
        "cat ~/.[a-z]sh/config",
        "ls ~/.config/*",
        "cat ~/.?nv",
    ],
)
def test_credential_wildcards_denied(cmd: str) -> None:
    assert denied(cmd)


def test_credential_wildcards_with_the_home_spelled_out(home: Path) -> None:
    assert denied(f"cp {home}/.* /tmp/x")
    assert denied(f"cp -r {home}/.??* /tmp/x")
    assert denied(f"cat {home}/.config/*/hosts.yml")


@pytest.mark.parametrize(
    "cmd",
    [
        "ls ~/*",
        "ls ~/projects/*",
        "cat ~/*ssh/config",
        "ls ~/.cache/*",
        "cat ~/.config/*.json",
        "ls ~/proj?cts",
        "cat ~/.bash*",
        "cat ~/.cargo/b*",
    ],
)
def test_wildcards_outside_credentials_allowed(cmd: str) -> None:
    assert not denied(cmd)


def test_wide_wildcards_only_in_home_or_a_credential_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    in_clean(tmp_path, monkeypatch)
    assert not denied("ls .*")
    assert not denied("ls .??*")
    assert not denied(f"ls {proj}/.*")
    assert not denied(f"cp -r {proj}/.??* /tmp/x")
    assert not denied("cat ./[0-9]*.md")


# --- 5. bare bracket classes are not literals -----------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "cat [a-z]*",
        "ls [a-z]*",
        "ls [A-Z]*",
        "git add [a-z]*",
        "ls ~/code/[a-z]*/",
        "wc -l [a-z]*",
        "cat ./[a-z]*.md",
    ],
)
def test_bare_bracket_class_not_a_credential(
    cmd: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_clean(tmp_path, monkeypatch)
    assert not denied(cmd)


@pytest.mark.parametrize(
    "cmd", ["cat proj/[i][d]_rsa", "cat proj/[a-z][a-z]_rsa", "cat proj/id_[a-z]sa", "cat p/*rsa"]
)
def test_bracket_class_with_literals_still_denied(cmd: str) -> None:
    assert denied(cmd)


def test_case_folded_glob_names_denied() -> None:
    assert denied("cat proj/.SS?/config")
    assert denied("cat proj/.AW*/credentials")


# --- 6. substitution, pipes, xargs, find -exec ----------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        'echo "$(cat d/f)"',
        'echo "`cat d/f`"',
        'echo "${x:-$(cat d/f)}"',
        'echo "a $(true) b $(cat d/f)"',
        'D=d; echo "$(cat $D/f)"',
        'cd d; echo "$(cat f)"',
        'echo "$(echo "$(cat d/f)")"',
    ],
)
def test_substitution_inside_double_quotes_is_scanned(cmd: str) -> None:
    assert denied(cmd)


@pytest.mark.parametrize(
    "cmd",
    ['echo "$(date)"', 'echo "$(cat plain.txt)"', 'echo "`pwd`"', 'echo "${x:-$(echo ok)}"'],
)
def test_substitution_inside_double_quotes_benign_allowed(cmd: str) -> None:
    assert not denied(cmd)


@pytest.mark.parametrize(
    "cmd",
    [
        "printf 'd/f\\n' | xargs cat",
        "ls d | xargs cat",
        "xargs -0 cat < list",
        "echo f | xargs -I{} cat d/{}",
        "sudo xargs cat",
        "ls | xargs grep -l token",
        "ls | xargs -n1 bash",
        "ls | xargs sed -n 1p",
    ],
)
def test_xargs_refused(cmd: str) -> None:
    assert check_rule(cmd) == "unscannable-path"


@pytest.mark.parametrize(
    "cmd",
    [
        "find d -name f -exec sh -c 'cat \"$1\"' _ {} \\;",
        "find . -exec bash -c 'cat {}' \\;",
        "find . -execdir sh -c x {} +",
        "find . -ok zsh -c x {} \\;",
    ],
)
def test_find_exec_of_a_shell_refused(cmd: str) -> None:
    assert check_rule(cmd) == "unscannable-path"


@pytest.mark.parametrize(
    "cmd",
    [
        "echo xargs",
        "xargs -n1 echo",
        "xargs",
        "ls | xargs pytest -q",
        "ls | xargs printf '%s\\n'",
        "find . -name '*.py' -exec wc -l {} +",
        "find . -type f -exec grep -l foo {} \\;",
        "ls | wc -l",
    ],
)
def test_xargs_and_find_neighbours_allowed(cmd: str) -> None:
    assert not denied(cmd)


@pytest.mark.parametrize(
    "cmd",
    [
        "head $(ls *docker*)",
        "cp $(echo gnupg*) /tmp/x",
        "tar c $(ls kube*)",
        "less $(echo npmrc)",
        "more `ls *kube*`",
        "mv $(echo pypirc) /tmp/x",
    ],
)
def test_reader_with_substitution_naming_a_credential_refused(cmd: str) -> None:
    assert check_rule(cmd) == "unscannable-path"


@pytest.mark.parametrize(
    "cmd",
    [
        "cat $(echo hello)",
        "cat $(git ls-files | head -1)",
        "echo $(ls *docker*)",
        "grep x $(ls *docker*)",
        "cat plain.txt $(date)",
    ],
)
def test_reader_with_unrelated_substitution_allowed(cmd: str) -> None:
    assert not denied(cmd)
