"""Proof for the judge-spread and low-consensus text in workflow-recipes.md section 3 (C10)."""

import json
import os
import re
import shutil
import subprocess
import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "skills/finhub-harness/references/workflow-recipes.md"
SRC = (
    "references/autogpt/classic/original_autogpt/autogpt/agents/prompt_strategies/"
    "multi_agent_debate.py:529"
)
OH = "references/openharness/src/openharness/hooks/executor.py:232"
Reply = dict[str, Any]  # what the node harness prints: r, prompts, logs, fed


def section3() -> str:
    text = DOC.read_text(encoding="utf-8")
    start = text.index("## 3. Judge panel")
    return text[start : text.index("## 4. Loop-until-dry")]


def test_section_attribution_and_keywords() -> None:
    s = section3()
    assert "### Reporting judge disagreement" in s
    assert f"adapted from {SRC} (MIT)" in s and f"adapted from {OH} (MIT)" in s
    for word in (
        "lowConsensus",
        "spreadLimit",
        "Never fill the gap",
        "does not apply there",
        "Do not ask the same judges",
        "adds no rounds",
        "9, 9, 5 flags; 9, 9, 6 does not",
        "reason to look, not proof",
        "winner only",
        "a panel of one judge is always flagged",
        "counts once per draft",
        "apart from the bare words ok, true and yes",
    ):
        assert word in s, word
    assert "strict JSON" not in s
    assert "return { finalDraft, lowConsensus, spread, n }" in s
    assert "drafts from 0 to 10:" in s
    # the bounds are killed by behaviour (0, 10, -0.5, -1, 10.0000001 tests); this pin is a backstop
    assert re.search(r"s >= 0\b|\b0 <= s", s) and re.search(r"s <= 10\b|\b10 >= s", s)


def test_prose_default_matches_code_default() -> None:
    s = section3()
    code = re.search(r"args\.spreadLimit : (\d+)", s)
    prose = re.search(r"The limit is (\d+) points", s)
    fallback = re.search(r"falls back to (\d+) rather", s)
    assert code and prose and fallback
    assert code.group(1) == prose.group(1) == fallback.group(1)


def test_no_hangul() -> None:
    ranges = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))
    text = DOC.read_text(encoding="utf-8")
    assert not any(lo <= ord(c) <= hi for c in text for lo, hi in ranges)


HARNESS = textwrap.dedent("""
    const code = require('fs').readFileSync(0, 'utf8')
    const sc = JSON.parse(process.argv[1])
    const marks = { __NaN__: NaN, __Inf__: Infinity, __NegInf__: -Infinity }
    const reply = j => j === null ? null : { scores: j.map(([i, s]) => {
      const score = typeof s === 'string' && s in marks ? marks[s] : s
      fed.push(String(score))
      return { index: i, strengths: 's', score } }) }
    const prompts = [], logs = [], fed = []
    const arg = v => (typeof v === 'string' && v in marks ? marks[v] : v)
    const body = code.replace(/^export const meta/m, 'const meta')
    const fn = new Function('agent', 'parallel', 'phase', 'log', 'args',
      'return (async () => {' + body + '})()')
    const agent = async (prompt, opts = {}) => {
      if (!opts.schema) return 'text'
      prompts.push(prompt)
      return reply(sc.judges[Number(opts.label.split(':')[1])])
    }
    const parallel = fns => Promise.all(fns.map(f => f()))
    fn(agent, parallel, () => {}, m => logs.push(m), { brief: 'b', ...Object.fromEntries(
      Object.entries(sc.args).map(([k, v]) => [k, arg(v)])) })
      .then(r => console.log(JSON.stringify({ r, prompts, logs, fed })))
    """)


def need_node() -> str:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("CI"):
            pytest.fail(
                "node is missing on CI: the recipe proof cannot run (add a setup-node step)"
            )
        pytest.skip("node not installed: the recipe scenarios are not proven on this machine")
    return node


def run(judges: list[Any], args: Mapping[str, Any] | None = None) -> Reply:
    """Run section 3's script with stub judges; each judge is a list of [draft index, score]."""
    block = re.search(r"```javascript\n(.*?)```", section3(), re.DOTALL)
    assert block, "no javascript block in section 3"
    scenario = json.dumps({"judges": judges, "args": args or {}})
    out = subprocess.run(
        [need_node(), "-e", HARNESS, scenario],
        input=block.group(1),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return cast(dict[str, Any], json.loads(out.stdout.strip().splitlines()[-1]))


def draft0(*scores: Any) -> list[Any]:
    """One stub judge per score: draft 0 gets that score, drafts 1 and 2 get 5."""
    return [[[0, s], [1, 5], [2, 5]] if s is not None else None for s in scores]


def verdict(judges: list[Any], args: Mapping[str, Any] | None = None) -> tuple[Any, Any, Any]:
    r = run(judges, args)["r"]
    return r["lowConsensus"], r["spread"], r["n"]


def test_split_panel_is_flagged() -> None:
    assert verdict(draft0(9, 2, 9)) == (True, 7, 3)


def test_invalid_replies_are_excluded_not_defaulted() -> None:
    assert verdict(draft0(9, "x", 9)) == (False, 0, 2)
    for bad in ("__NaN__", "__Inf__", "__NegInf__", -1, 99, "9", True, 10.0000001):
        assert verdict(draft0(9, bad, 9)) == (False, 0, 2), bad


def test_single_valid_score_is_low_consensus() -> None:
    assert verdict(draft0(9, None, None)) == (True, 0, 1)


def test_threshold_boundary_and_three_judge_examples() -> None:
    assert verdict(draft0(8, 9, 8))[0] is False
    assert verdict(draft0(9, 9, 6)) == (False, 3, 3)
    assert verdict(draft0(9, 9, 5)) == (True, 4, 3)
    assert verdict(draft0(10, 0, 10)) == (True, 10, 3)


def test_spread_limit_override_and_garbage_fallback() -> None:
    assert verdict(draft0(9, 9, 5), {"spreadLimit": 5})[0] is False
    assert verdict(draft0(8, 9.5, 8), {"spreadLimit": 1})[0] is True
    assert verdict(draft0(8, 9, 8), {"spreadLimit": 1})[0] is False  # equal is not above
    for garbage in ("abc", "3", None):
        assert verdict(draft0(9, 2, 9), {"spreadLimit": garbage})[0] is True, garbage
        assert verdict(draft0(8, 9, 8), {"spreadLimit": garbage})[0] is False, garbage


def test_flag_is_read_from_the_winner_not_the_first_draft() -> None:
    judges = [[[0, 5], [1, s], [2, 5]] for s in (9, 2, 9)]  # draft 1 wins with spread 7
    assert verdict(judges) == (True, 7, 3)


def test_each_judge_counts_once_per_draft() -> None:
    dup = [[0, 9], [0, 2], [1, 5], [2, 5]]  # same index twice: the first valid entry wins
    others = draft0(9, 9)
    assert verdict([dup, *others]) == (False, 0, 3)
    assert verdict([dup, None, None]) == (True, 0, 1)
    first_bad = [[0, "x"], [0, 9], [1, 5], [2, 5]]  # an invalid first entry is skipped, not used
    assert verdict([first_bad, *others]) == (False, 0, 3)


def test_prompt_scale_log_line_and_single_judge() -> None:
    flagged = run(draft0(9, 2, 9))
    assert all("from 0 to 10:" in p for p in flagged["prompts"]) and flagged["prompts"]
    assert any("Low consensus: 3 valid scores, spread 7" in m for m in flagged["logs"])
    assert not any("Low consensus" in m for m in run(draft0(8, 9, 8))["logs"])
    assert verdict(draft0(9), {"judgeCount": 1}) == (True, 0, 1)


def test_ties_return_the_first_maximum_and_error_paths_keep_their_shape() -> None:
    tie = [[[0, 5], [1, 5], [2, 5]]] * 3
    assert verdict(tie) == (False, 0, 3)
    assert run([None, None, None])["r"]["error"] == "There are no completed judging results."


def test_mean_tie_first_maximum_wins() -> None:
    # draft 0 scores 7,7,7 and draft 1 scores 10,10,1: equal means, so draft 0 (spread 0) wins
    judges = [[[0, 7], [1, 10], [2, 1]]] * 2 + [[[0, 7], [1, 1], [2, 1]]]
    assert verdict(judges) == (False, 0, 3)


def test_skipped_score_stays_out_of_the_mean() -> None:
    # the third judge omits draft 0: draft 0 stays on mean 9 from n 2, not 6 from a zero fill
    judges = [[[0, 9], [1, 7], [2, 1]]] * 2 + [[[1, 7], [2, 1]]]
    assert verdict(judges) == (False, 0, 2)


def test_every_score_invalid_gives_the_structured_error() -> None:
    bad = [[[i, s] for i in range(3)] for s in ("__NaN__", "x", -1)]
    r = run(bad)["r"]
    assert r["error"] == "There are no valid per-draft scores."
    assert len(r["drafts"]) == 3 and "finalDraft" not in r


def test_real_nan_and_infinity_reach_the_recipe_and_are_excluded() -> None:
    nan = run(draft0(9, "__NaN__", 9))
    assert "NaN" in nan["fed"]
    inf = run(draft0(9, "__Inf__", 9))
    assert "Infinity" in inf["fed"]
    for out in (nan, inf):
        r = out["r"]
        assert (r["lowConsensus"], r["spread"], r["n"]) == (False, 0, 2)
    assert "-Infinity" in run(draft0(9, "__NegInf__", 9))["fed"]


def test_non_finite_spread_limit_falls_back_and_index_is_strict() -> None:
    assert verdict(draft0(9, 2, 9), {"spreadLimit": "__NaN__"})[0] is True
    assert verdict(draft0(9, 2, 9), {"spreadLimit": "__Inf__"})[0] is True
    string_index = [[["0", 2], [1, 5], [2, 5]], *draft0(9, 9)]  # "0" is not the integer 0
    assert verdict(string_index) == (False, 0, 2)


def test_prose_sentences_are_bound_to_the_code() -> None:
    s = section3()
    below = re.search(r"`n` is below (\d+)", s)
    code = re.search(r"n < (\d+) \|\|", s)
    assert below and code and below.group(1) == code.group(1)
    assert "its first valid entry is used" in s  # find() takes the first valid entry
    assert "does not make judges agree or change the pick" in s
    assert "highest valid score minus the lowest" in s
    ex = re.search(r"(\d+), (\d+) and (\d+) average the same (\d+\.\d)", s)
    assert ex and round(sum(map(int, ex.groups()[:3])) / 3, 1) == float(ex.group(4))


def test_mean_divisor_is_the_number_of_scores() -> None:
    # draft 1 is skipped by one judge: 9,9 from n 2 must still beat draft 0 on 8,8
    skipped = [[[0, 8], [1, 9], [2, 5]]] * 2 + [[[0, 8], [2, 5]]]
    assert verdict(skipped) == (False, 0, 2)
    # draft 0 scores 9,9,1 (mean 6.33, spread 8) and beats 6,6,6
    assert verdict([[[0, 9], [1, 6], [2, 1]]] * 2 + [[[0, 1], [1, 6], [2, 1]]]) == (True, 8, 3)


def test_tie_goes_to_the_first_draft_whatever_its_spread_or_judge_count() -> None:
    # drafts 0 and 1 tie on mean 7; draft 0 has the larger spread and still wins
    wide = [[[0, 9], [1, 7], [2, 1]], [[0, 5], [1, 7], [2, 1]], [[0, 7], [1, 7], [2, 1]]]
    assert verdict(wide) == (True, 4, 3)
    # a gap of 1 between means is a win for the later draft (no tolerance on the comparison)
    near = [[[0, 7], [1, 7], [2, 1]]] * 2 + [[[0, 7], [1, 8], [2, 1]]]
    assert verdict(near) == (False, 1, 3)
    # equal means, draft 0 scored by 3 judges and draft 1 by 2: draft 0
    assert verdict([[[0, 7], [1, 7]]] * 2 + [[[0, 7]]]) == (False, 0, 3)
    # equal means, draft 0 scored by 2 judges and draft 1 by 3: still draft 0
    assert verdict([[[0, 7], [1, 7]]] * 2 + [[[1, 7]]]) == (False, 0, 2)


def test_flag_with_two_scores_uses_the_plain_limit() -> None:
    assert verdict(draft0(9, 2, None)) == (True, 7, 2)
    assert verdict(draft0(9, 6, None)) == (False, 3, 2)


def test_spread_limit_zero_and_above_ten_are_honoured() -> None:
    assert verdict(draft0(8, 9, 8), {"spreadLimit": 0}) == (True, 1, 3)
    assert verdict(draft0(10, 0, 10), {"spreadLimit": 50})[0] is False


def test_all_invalid_error_carries_the_judged_replies() -> None:
    r = run([[[i, "x"] for i in range(3)]] * 3)["r"]
    assert r["error"] == "There are no valid per-draft scores."
    assert len(r["judged"]) == 3 and r["judged"][0]["scores"][0]["score"] == "x"


def test_score_just_below_zero_is_excluded() -> None:
    assert verdict(draft0(9, -0.5, 9)) == (False, 0, 2)
    assert verdict(draft0(9, -0.0000001, 9)) == (False, 0, 2)
