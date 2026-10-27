"""The agent loop (:mod:`dragon.agent.core`) and the hold registry
(:mod:`dragon.agent.holds`). ``core`` pulls in the Sentinel and the tools, and the tools
import ``holds``; so ``core`` is loaded on first use rather than here, and
``from dragon.agent.holds import Holds`` works from anywhere without a cycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dragon.agent.core import DragonAgent, Incoming

__all__ = ["Incoming", "DragonAgent"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from dragon.agent import core

        return getattr(core, name)
    raise AttributeError(f"module 'dragon.agent' has no attribute {name!r}")
