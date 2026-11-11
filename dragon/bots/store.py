"""Bot store: the personas chats speak as, kept in ``<data_dir>/bots.json``.

A bot is a JSON object (the shape the API and the web app exchange):

    {
        "id": "b_1a2b3c4d",        # "b_" + 8 lowercase hex, except the default bot: "default"
        "role": "staff",           # "chief" for the default bot, "staff" for every other one
        "name": "Ember",
        "avatar": "dragon",        # "dragon", a studio face id, or "" (the emoji)
        "emoji": "",
        "color": "",
        "tagline": "",
        "tone": "warm",            # a key of TONES (dragon/prompts.py), or ""
        "communication": "",
        "style": "",
        "instructions": "",
        "model": "",               # kept for later; the runtime does not route per bot yet
        "created_at": 1761000000   # unix seconds
    }

The default bot (``id == "default"``) always exists: it is the bot every thread speaks
as unless the thread names another one. On a first load it is seeded from the persona in
``profile.json`` (see ``DragonService``), so an existing install keeps its identity.
``role`` is server-owned: it is derived from the id — the default bot is the user's chief
of staff, every other bot is on its staff — and never read from the data, so a request
that sends a role cannot promote a bot or demote the chief. Files written before the role
existed load fine and are rewritten in the new shape.
Writes go through a temporary file and ``os.replace``, the pattern the session files use.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from dragon.prompts import COMMUNICATION, TONES

DEFAULT_BOT_ID = "default"
DEFAULT_BOT_NAME = "Ember"
# roles: the default bot is the user's chief of staff, every other bot is on its staff.
# Derived from the id, never taken from the data (see normalize).
ROLE_CHIEF = "chief"
ROLE_STAFF = "staff"
ROLES = (ROLE_CHIEF, ROLE_STAFF)
# identity limits, the same ones the profile keeps (the app's forms share them)
NAME_MAX = 20
TAGLINE_MAX = 60
STYLE_MAX = 1000
INSTRUCTIONS_MAX = 4000
MODEL_MAX = 200
BOT_ID_RE = re.compile(r"b_[0-9a-f]{8}")
# the fields a bot owns; everything else in the data is ignored. ``role`` is among them
# but server-owned: it is written from the id, never from what a caller sends.
BOT_FIELDS = (
    "name",
    "avatar",
    "emoji",
    "color",
    "tagline",
    "tone",
    "communication",
    "style",
    "instructions",
    "model",
    "role",
)


def new_bot_id() -> str:
    return "b_" + uuid.uuid4().hex[:8]


def role_of(bot_id: str) -> str:
    """A bot's role from its id: the chief of staff for the default bot, staff otherwise.
    This is the only place a role comes from, so only "chief" and "staff" ever exist."""
    return ROLE_CHIEF if str(bot_id or "") == DEFAULT_BOT_ID else ROLE_STAFF


def _clean_name(value: Any, required: bool) -> str:
    name = " ".join(str(value or "").split())[:NAME_MAX]
    if not name and required:
        raise ValueError("a bot needs a name")
    return name


def _clean_avatar(value: Any) -> str:
    return re.sub(r"[^a-z0-9-]", "", str(value or "").lower())[:32]


def _clean_choice(value: Any, vocabulary: dict[str, str]) -> str:
    """A tone or communication choice: a key of its vocabulary, or "" for "not set"."""
    choice = str(value or "").strip().lower()
    if choice and choice not in vocabulary:
        raise ValueError(f"unknown choice {choice!r}; expected one of {', '.join(vocabulary)}")
    return choice


def _clean_text(value: Any, limit: int) -> str:
    return str(value if value is not None else "")[:limit]


def normalize(
    data: dict[str, Any], *, require_name: bool = False, bot_id: str = ""
) -> dict[str, Any]:
    """One bot JSON object, validated and trimmed. Unknown fields are ignored.

    ``role`` is server-owned: it comes from ``bot_id`` ("chief" for the default bot,
    "staff" for every other one) and is never read from ``data`` — a request that sends
    one is ignored. ``name`` is required for a new bot; ``tone`` must be a key of ``TONES``
    (or ""); ``communication`` likewise. Raises :class:`ValueError` when a value cannot
    be kept.
    """
    bot: dict[str, Any] = {
        "id": bot_id,
        "role": role_of(bot_id),
        "name": _clean_name(data.get("name"), require_name),
        "avatar": _clean_avatar(data.get("avatar")),
        "emoji": _clean_text(data.get("emoji"), 8),
        "color": _clean_text(data.get("color"), 16),
        "tagline": " ".join(str(data.get("tagline") or "").split())[:TAGLINE_MAX],
        "tone": _clean_choice(data.get("tone"), TONES),
        "communication": _clean_choice(data.get("communication"), COMMUNICATION),
        "style": _clean_text(data.get("style"), STYLE_MAX),
        "instructions": _clean_text(data.get("instructions"), INSTRUCTIONS_MAX),
        "model": str(data.get("model") or "").strip()[:MODEL_MAX],
        "created_at": int(data.get("created_at") or 0),
    }
    return bot


class BotStore:
    """CRUD over ``bots.json``, with the default bot always present."""

    def __init__(self, path: Path | str, seed: dict[str, Any] | None = None):
        self.path = Path(path)
        self._bots: dict[str, dict[str, Any]] = {}
        rewrite = self._load()
        if DEFAULT_BOT_ID not in self._bots:
            # a first load (or a file that lost its default bot): the persona comes from
            # ``seed`` — the profile's identity fields — else from the built-in defaults
            base: dict[str, Any] = {"name": DEFAULT_BOT_NAME, "avatar": "dragon"}
            base.update({k: v for k, v in (seed or {}).items() if v is not None})
            if not str(base.get("name") or "").strip():
                base["name"] = DEFAULT_BOT_NAME
            self._bots[DEFAULT_BOT_ID] = normalize(base, require_name=True, bot_id=DEFAULT_BOT_ID)
            self._bots[DEFAULT_BOT_ID]["created_at"] = int(time.time())
            rewrite = True
        if rewrite:
            self._save()

    # ------------------------------------------------------------------ persistence
    def _load(self) -> bool:
        """Read the file into ``self._bots``; ``True`` when it should be rewritten (an
        entry without a role, or one whose role the id contradicts)."""
        if not self.path.exists():
            return False
        try:
            data = json.loads(self.path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            self._preserve_corrupt()
            return False
        entries = data.get("bots", []) if isinstance(data, dict) else []
        rewrite = False
        for item in entries:
            if not isinstance(item, dict):
                continue
            bot_id = str(item.get("id") or "")
            if not (bot_id == DEFAULT_BOT_ID or BOT_ID_RE.fullmatch(bot_id)):
                continue
            try:
                bot = normalize(item, require_name=True, bot_id=bot_id)
            except ValueError:
                continue
            bot["created_at"] = int(item.get("created_at") or 0) or int(time.time())
            # a file from before roles existed, or one that disagrees with the id: the
            # id is authoritative and the file is rewritten in the new shape
            rewrite = rewrite or item.get("role") != bot["role"]
            self._bots[bot_id] = bot
        return rewrite

    def _preserve_corrupt(self) -> None:
        """Rename an unreadable file aside instead of letting the next save overwrite it,
        so staff bots are never silently lost to a truncated write."""
        try:
            self.path.rename(self.path.with_name(f"{self.path.name}.corrupt"))
        except OSError:  # pragma: no cover - best effort; a missing file is fine
            pass

    def _save(self) -> None:
        """Write the file atomically: a temporary file beside it, then ``os.replace``."""
        keep = [self._bots[bid] for bid in self._order()]
        text = json.dumps({"version": 1, "bots": keep}, ensure_ascii=False, indent=1)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _order(self) -> list[str]:
        """Default bot first, then oldest first, so the list is stable across saves."""
        rest = sorted(
            (b for b in self._bots.values() if b["id"] != DEFAULT_BOT_ID),
            key=lambda b: (b["created_at"], b["id"]),
        )
        return [DEFAULT_BOT_ID, *(b["id"] for b in rest)]

    # ------------------------------------------------------------------ queries
    def list(self) -> list[dict[str, Any]]:
        return [dict(self._bots[bid]) for bid in self._order() if bid in self._bots]

    def get(self, bot_id: str) -> dict[str, Any] | None:
        bot = self._bots.get(str(bot_id or ""))
        return dict(bot) if bot is not None else None

    @property
    def default_id(self) -> str:
        return DEFAULT_BOT_ID

    # ------------------------------------------------------------------ mutations
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """A new bot with an id of its own; ``name`` is required, and it joins the staff
        (``role`` is always "staff" — the chief is the default bot). A client-supplied id
        is ignored — the store mints ids so they cannot collide or impersonate."""
        bot = normalize(data, require_name=True, bot_id="")
        while not bot["id"]:
            candidate = new_bot_id()
            if candidate not in self._bots:
                bot["id"] = candidate
        bot["created_at"] = int(time.time())
        self._bots[bot["id"]] = bot
        self._save()
        return dict(bot)

    def update(self, bot_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Merge ``data`` into one bot (:class:`KeyError` for an unknown id). Only the
        fields present change; ``id``, ``created_at``, ``role`` (server-owned) and unknown
        fields are ignored."""
        bot = self._bots.get(str(bot_id or ""))
        if bot is None:
            raise KeyError(bot_id)
        changes: dict[str, Any] = {}
        for key in BOT_FIELDS:
            if key == "role":
                continue  # server-owned: a caller never sets it
            if key in data and data[key] is not None:
                changes[key] = data[key]
        if "name" in changes:
            changes["name"] = _clean_name(changes["name"], required=True)
        merged = normalize({**bot, **changes}, require_name=True, bot_id=bot["id"])
        merged["created_at"] = bot["created_at"]
        self._bots[bot["id"]] = merged
        self._save()
        return dict(merged)

    def delete(self, bot_id: str) -> None:
        """Remove a bot (:class:`KeyError` for an unknown id). Refused with
        :class:`ValueError` for the default bot and for the last bot — one bot always
        speaks for the runtime."""
        bot = self._bots.get(str(bot_id or ""))
        if bot is None:
            raise KeyError(bot_id)
        if bot["id"] == DEFAULT_BOT_ID:
            raise ValueError("the default bot cannot be deleted")
        if len(self._bots) <= 1:
            raise ValueError("the last bot cannot be deleted")
        del self._bots[bot["id"]]
        self._save()


__all__ = [
    "BOT_FIELDS",
    "BOT_ID_RE",
    "DEFAULT_BOT_ID",
    "DEFAULT_BOT_NAME",
    "ROLES",
    "ROLE_CHIEF",
    "ROLE_STAFF",
    "BotStore",
    "new_bot_id",
    "normalize",
    "role_of",
]
