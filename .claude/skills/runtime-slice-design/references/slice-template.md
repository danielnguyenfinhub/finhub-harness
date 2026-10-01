# Slice template

Every slice in `02_strategy-architect_slices.md` uses these sections in this order. Example filled with slice 1; values are synthetic.

~~~markdown
## Slice 1 — agent loop + echo tool + CLI

### Goal
Daniel runs `python -m master_finhub.cli "echo hi"` and sees `hi` — proves the loop can call a tool and stop.

### Files
| path | new/modified |
|---|---|
| src/master_finhub/runtime/loop.py | new |
| src/master_finhub/tools/builtins/echo.py | new |
| src/master_finhub/cli.py | new |
| tests/test_loop.py | new |

### Interfaces
```python
class LLM(Protocol):
    def turn(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> Turn: ...

@dataclass(frozen=True)
class ToolSpec:
    name: str
    params: Mapping[str, type]        # declared schema the loop validates args against

@dataclass(frozen=True)
class ToolCall:
    name: str
    args: Mapping[str, object]

def run(llm: LLM, tools: Mapping[str, Tool], prompt: str, max_steps: int = 20) -> str: ...
```

### Behaviour (claims → Authority List)
- Loop: preStep → model turn → execute tool calls → append results; stop when a turn has no tool calls (A1).
- Unknown tool or args not matching `ToolSpec.params` → tool-result error message, not an exception (A2, NET-NEW).
- `max_steps` reached → return last assistant text plus `[stopped: step limit]`.

### Proof
- `tests/test_loop.py::test_echo_round_trip` — `FakeLLM` scripted to call `echo(text="hi")` then answer; `run(...) == "hi"`.
- `python -m master_finhub.cli "echo hi"` prints `hi`, exit 0.

### Dependencies
None (stdlib only).

### Ported vs net-new
| part | source | port as |
|---|---|---|
| loop shape | D1 (deepseek agent-loop) | adapt |
| arg validation | — | net-new |

### Quant guardrails
Not applicable (no pricing, returns or data splits in this slice).

### Out of scope
Real LLM providers (slice 4), compaction (slice 2), sandboxing (slice 3).
~~~

## Section rules

| section | rule |
|---|---|
| Goal | One sentence in Daniel's terms: what he runs and sees |
| Files | Only `src/master_finhub/**`, `tests/**`, `pyproject.toml` |
| Interfaces | Typed Python signatures; these are the contract boundary-qa compares |
| Behaviour | Each bullet tagged with Authority List ids |
| Proof | One test and/or one command; exact expected output |
| Dependencies | Name + why stdlib cannot do it; adding one is AMBER for the builder |
| Quant guardrails | For eval/verifier/backtest/pricing slices: one line per guardrail from quant-guardrails.md; otherwise "Not applicable" with reason |
| Out of scope | What the next slices own, so the builder does not drift |
