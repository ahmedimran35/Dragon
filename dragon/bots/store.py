"""Bot store: the personas chats speak as, kept in ``<data_dir>/bots.json``.

A bot is a JSON object (the shape the API and the web app exchange):

    {
        "id": "b_1a2b3c4d",        # "b_" + 8 lowercase hex, except the default bot: "default"
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
# identity limits, the same ones the profile keeps (the app's forms share them)
NAME_MAX = 20
TAGLINE_MAX = 60
STYLE_MAX = 1000
INSTRUCTIONS_MAX = 4000
MODEL_MAX = 200
BOT_ID_RE = re.compile(r"b_[0-9a-f]{8}")
# the fields a bot owns; everything else in the data is ignored
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
)


def new_bot_id() -> str:
    return "b_" + uuid.uuid4().hex[:8]


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

    ``name`` is required for a new bot; ``tone`` must be a key of ``TONES`` (or "");
    ``communication`` likewise. Raises :class:`ValueError` when a value cannot be kept.
    """
    bot: dict[str, Any] = {
        "id": bot_id,
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
        self._load()
        if DEFAULT_BOT_ID not in self._bots:
            # a first load (or a file that lost its default bot): the persona comes from
            # ``seed`` — the profile's identity fields — else from the built-in defaults
            base: dict[str, Any] = {"name": DEFAULT_BOT_NAME, "avatar": "dragon"}
            base.update({k: v for k, v in (seed or {}).items() if v is not None})
            if not str(base.get("name") or "").strip():
                base["name"] = DEFAULT_BOT_NAME
            self._bots[DEFAULT_BOT_ID] = normalize(base, require_name=True, bot_id=DEFAULT_BOT_ID)
            self._bots[DEFAULT_BOT_ID]["created_at"] = int(time.time())
            self._save()

    # ------------------------------------------------------------------ persistence
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        entries = data.get("bots", []) if isinstance(data, dict) else []
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
            self._bots[bot_id] = bot

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
        """A new bot with an id of its own; ``name`` is required. A client-supplied id is
        ignored — the store mints ids so they cannot collide or impersonate."""
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
        fields present change; ``id``, ``created_at`` and unknown fields are ignored."""
        bot = self._bots.get(str(bot_id or ""))
        if bot is None:
            raise KeyError(bot_id)
        changes: dict[str, Any] = {}
        for key in BOT_FIELDS:
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
    "BotStore",
    "new_bot_id",
    "normalize",
]
