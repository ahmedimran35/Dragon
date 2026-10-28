"""Bots: the personas chats speak as, and the roles of the chief of staff.

Every bot has a ``role``: the default bot (``id == "default"``) is the user's chief of
staff, every other bot is on its staff. The role is server-owned — derived from the id in
:meth:`~dragon.bots.store.normalize`, never read from what a caller sends.

:class:`~dragon.bots.store.BotStore` keeps them in ``<data_dir>/bots.json``. A thread is
bound to one bot and the agent loop builds its identity (name, tone, style, standing
instructions) from it. The running bot also reaches the tools: a tool that needs to know
whose turn it is (``remember`` tags memories with it) reads :func:`running_bot_id`, the
same way the conversation reaches tools through ``current_thread`` (a ContextVar set for
the duration of a run).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from dragon.bots.store import (
    BOT_FIELDS,
    BOT_ID_RE,
    DEFAULT_BOT_ID,
    DEFAULT_BOT_NAME,
    ROLE_CHIEF,
    ROLE_STAFF,
    ROLES,
    BotStore,
    new_bot_id,
    normalize,
    role_of,
)

# whose turn is running: set by DragonAgent.run for the duration of one run, so every
# tool call of that run knows the bot it belongs to (default: the default bot)
current_bot_id: ContextVar[str] = ContextVar("dragon_bot_id", default=DEFAULT_BOT_ID)
# the bot object of that run, for whoever needs more than the id (its name, say)
current_bot: ContextVar[dict[str, Any] | None] = ContextVar("dragon_bot", default=None)


def running_bot_id() -> str:
    """The id of the bot whose turn is running; the default bot outside any run."""
    return current_bot_id.get() or DEFAULT_BOT_ID


def running_bot() -> dict[str, Any] | None:
    """The bot object of the running turn, or None outside one."""
    return current_bot.get()


__all__ = [
    "BOT_FIELDS",
    "BOT_ID_RE",
    "DEFAULT_BOT_ID",
    "DEFAULT_BOT_NAME",
    "ROLES",
    "ROLE_CHIEF",
    "ROLE_STAFF",
    "BotStore",
    "current_bot",
    "current_bot_id",
    "new_bot_id",
    "normalize",
    "role_of",
    "running_bot",
    "running_bot_id",
]
