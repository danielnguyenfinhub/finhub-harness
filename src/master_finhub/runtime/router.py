"""Model-tier router: job profile -> Claude tier -> model id (slice 4).

Stdlib only at import time; the Anthropic adapter is imported lazily in ``build_llm``.
Ideas ported (not code) from MIT-licensed deepseek-harness
``references/deepseek_harness/packages/llm/llm/src/types.ts:343`` (route + model on a request),
``.../llm-pi-ai/src/config.ts:379`` (validated route dict) and ``.../adapter.ts:242,252``
(unknown route and unknown model are distinct loud failures). The profile -> tier layer is
net-new: no reference has one (Daniel's CLAUDE.md section 8 and .claude/agents/*.md).
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal

from master_finhub.runtime.loop import LLM

if TYPE_CHECKING:
    import httpx2

Tier = Literal["opus", "sonnet", "haiku"]
Provider = Literal["anthropic"]

PROVIDER: Final[Provider] = "anthropic"
DEFAULT_MAX_TOKENS: Final = 8192
# Hard per-call output ceiling. The SDK refuses non-streaming calls above this when it owns the
# timeout (anthropic/resources/messages/messages.py:1001, _base_client.py:782). The adapter sets
# its own timeout, which bypasses that SDK check, so this ceiling is enforced here instead.
MAX_NONSTREAMING_TOKENS: Final = 21_333

# THE one place model ids live. Overridable per Router instance.
DEFAULT_TIER_MODELS: Final[Mapping[Tier, str]] = MappingProxyType(
    {
        "opus": "claude-opus-5-5",
        "sonnet": "claude-sonnet-5-5",
        "haiku": "claude-haiku-4-5-20251001",
    }
)
# Profile -> tier, from CLAUDE.md section 8 and .claude/agents/*.md "Model tier" lines.
DEFAULT_PROFILE_TIERS: Final[Mapping[str, Tier]] = MappingProxyType(
    {
        "judge": "opus",
        "strategy-architect": "opus",
        "miner": "sonnet",
        "builder": "sonnet",
        "qa": "sonnet",
        "grunt": "haiku",
    }
)


class RouterConfigError(ValueError):
    """Bad router table or setting. Message is three-part: what / Why / Fix."""


class UnknownProfileError(RouterConfigError):
    """The requested profile is not in the router's profile table."""


def _three_part(what: str, why: str, fix: str) -> str:
    return f"{what}\nWhy: {why}\nFix: {fix}"


@dataclass(frozen=True)
class ModelChoice:
    profile: str
    provider: Provider
    tier: Tier
    model: str
    max_tokens: int


@dataclass(frozen=True)
class Router:
    tier_models: Mapping[Tier, str] = field(default_factory=lambda: DEFAULT_TIER_MODELS)
    profiles: Mapping[str, Tier] = field(default_factory=lambda: DEFAULT_PROFILE_TIERS)
    max_tokens: int = DEFAULT_MAX_TOKENS

    def __post_init__(self) -> None:
        tiers, profiles = dict(self.tier_models), dict(self.profiles)
        if not tiers or not profiles:
            raise RouterConfigError(
                _three_part(
                    "The router tables are empty.",
                    "a router needs at least one tier and one profile.",
                    "pass Router() for the defaults, or non-empty tier_models and profiles.",
                )
            )
        if any(not k or not v for k, v in [*tiers.items(), *profiles.items()]):
            raise RouterConfigError(
                _three_part(
                    "A router table has an empty name or model id.",
                    "every profile, tier and model id must be a non-empty string.",
                    "remove or fill the blank entry in tier_models / profiles.",
                )
            )
        missing = sorted(p for p, t in profiles.items() if t not in tiers)
        if missing:
            bad = sorted({profiles[p] for p in missing})
            raise RouterConfigError(
                _three_part(
                    f"Profile(s) {', '.join(missing)} point at tier(s) {', '.join(bad)} "
                    "that have no model.",
                    "every profile's tier must exist in tier_models.",
                    "add the tier to tier_models or point the profile at an existing tier.",
                )
            )
        if not 1 <= self.max_tokens <= MAX_NONSTREAMING_TOKENS:
            raise RouterConfigError(
                _three_part(
                    f"max_tokens={self.max_tokens} is outside the allowed range.",
                    f"one reply may use 1 to {MAX_NONSTREAMING_TOKENS} output tokens "
                    "(a hard cost and time ceiling per call).",
                    f"use a value between 1 and {MAX_NONSTREAMING_TOKENS}.",
                )
            )
        object.__setattr__(self, "tier_models", MappingProxyType(tiers))
        object.__setattr__(self, "profiles", MappingProxyType(profiles))

    def resolve(self, profile: str) -> ModelChoice:
        tier = self.profiles.get(profile)
        if tier is None:
            close = difflib.get_close_matches(profile, list(self.profiles), n=3, cutoff=0.6)
            hint = f" (closest: {', '.join(close)})" if close else ""
            raise UnknownProfileError(
                _three_part(
                    f"Unknown model profile '{profile}'{hint}.",
                    f"the router only maps these profiles: {', '.join(sorted(self.profiles))}.",
                    f"use one of those names, or add it with Router(profiles={{..., "
                    f"'{profile}': 'opus'}}).",
                )
            )
        return ModelChoice(profile, PROVIDER, tier, self.tier_models[tier], self.max_tokens)

    def build_llm(
        self,
        profile: str,
        *,
        system: str = "",
        max_retries: int | None = None,
        transport: httpx2.BaseTransport | None = None,
    ) -> LLM:
        """Resolve ``profile`` and build the real provider. Imports the SDK adapter lazily."""
        from master_finhub.runtime.anthropic_llm import DEFAULT_MAX_RETRIES, AnthropicLLM

        choice = self.resolve(profile)
        return AnthropicLLM(
            choice.model,
            max_tokens=choice.max_tokens,
            system=system,
            max_retries=DEFAULT_MAX_RETRIES if max_retries is None else max_retries,
            transport=transport,
        )
