"""Which conversation a model call belongs to, for the vendors that want to be told.

OpenCode Go asks every client to name itself with its own user agent and to send one stable
id per conversation in ``x-opencode-session`` (opencode.ai/docs/go, "Where can I use it?").
The catalogue names such a header in an entry's ``session_header``; the chat clients add it
to each request with :func:`session_id`, and name Dragon with :data:`USER_AGENT`.

The agent loop says which conversation it is working on with :func:`conversation`, a context
variable, so every call made while the turn runs (the hands' model included) carries the
same id without threading it through each ``ask``. A call made outside a conversation (a
connection test, a background summary) carries the client's own id instead, stable for as
long as the client lives.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from dragon import __version__

_conversation: ContextVar[str | None] = ContextVar("dragon_conversation", default=None)


#: what a header value may be as it is: visible ASCII, short enough for any gateway
_HEADER_SAFE = re.compile(r"^[\x21-\x7e]{1,128}$")
_NAMESPACE = uuid.UUID("5b0f7c1e-3a52-4f4e-9d0e-6e616e6f4d75")

#: the user agent Dragon names itself with on every model call
USER_AGENT = f"Dragon/{__version__}"


@contextmanager
def conversation(conversation_id: str) -> Iterator[None]:
    """Model calls made inside the block belong to this conversation."""
    token = _conversation.set(conversation_id)
    try:
        yield
    finally:
        _conversation.reset(token)


def enter(conversation_id: str) -> Token[str | None]:
    """:func:`conversation` for a caller whose block is a ``try``: pass the token to
    :func:`leave` in its ``finally``."""
    return _conversation.set(conversation_id)


def leave(token: Token[str | None]) -> None:
    _conversation.reset(token)


def current_conversation() -> str | None:
    return _conversation.get()


def session_id(fallback: str) -> str:
    """The id to send for the current call: the conversation's, else ``fallback``. An id that
    is not a safe header value (spaces, non-ASCII, very long) is sent as a UUID derived from
    it, so it stays the same for the same conversation."""
    raw = _conversation.get() or fallback
    return raw if _HEADER_SAFE.match(raw) else str(uuid.uuid5(_NAMESPACE, raw))


def client_headers(extra: dict[str, str] | None, session_header: str = "") -> dict[str, str]:
    """The headers a client sends on every request: the slot's ``extra_headers``, plus
    Dragon's own user agent (one the person set in ``extra_headers`` stands). A vendor with
    a session header (OpenCode Go) asks for the name outright."""
    headers = dict(extra or {})
    if not any(k.lower() == "user-agent" for k in headers):
        headers["User-Agent"] = USER_AGENT
    return headers


def new_fallback() -> str:
    """A client's own id, for the calls made outside any conversation."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------- turns and trajectories

#: who started the turn, as a short word (``person``, ``schedule``, ``feed``, ``goal``)
RUNS = ("person", "schedule", "feed", "goal")
RUN_OF_SOURCE = {
    "user": "person",
    "goal": "goal",
    "reminder": "schedule",
    "trigger": "schedule",
    "routine": "schedule",
    "feed": "feed",
}


class Turn:
    """One turn of a conversation as the agent loop runs it: who started it, its number,
    and a counter of the model calls made within it (the hands' included)."""

    __slots__ = ("run", "number", "calls")

    def __init__(self, run: str = "person", number: int = 0) -> None:
        self.run = run if run in RUNS else "person"
        self.number = max(0, int(number))
        self.calls = 0


class Trajectory:
    """One screen-operation task: its id (the operator's trace id) and the step under way."""

    __slots__ = ("id", "step")

    def __init__(self, trajectory_id: str = "") -> None:
        self.id = trajectory_id
        self.step = 0


_turn: ContextVar[Turn | None] = ContextVar("dragon_turn", default=None)
_trajectory: ContextVar[Trajectory | None] = ContextVar("dragon_trajectory", default=None)
_run_only: ContextVar[str] = ContextVar("dragon_run", default="")


def run_of(source: str) -> str:
    """The short word for a message's ``source`` (``user``, ``goal``, ``reminder``, …)."""
    return RUN_OF_SOURCE.get(source, "schedule" if source else "person")


@contextmanager
def turn(run: str, number: int) -> Iterator[Turn]:
    """Model calls made inside the block belong to turn ``number`` of the conversation,
    started by ``run`` (one of :data:`RUNS`)."""
    t = Turn(run, number)
    token = _turn.set(t)
    try:
        yield t
    finally:
        _turn.reset(token)


def begin_turn(run: str, number: int) -> Token[Turn | None]:
    """:func:`turn` for a caller whose block is a ``try``: pass the token to :func:`end_turn`."""
    return _turn.set(Turn(run, number))


def end_turn(token: Token[Turn | None]) -> None:
    _turn.reset(token)


@contextmanager
def run(kind: str) -> Iterator[None]:
    """Calls made inside the block were started by ``kind`` (a routine's single call, made
    outside the agent loop: the feed)."""
    token = _run_only.set(kind if kind in RUNS else "schedule")
    try:
        yield
    finally:
        _run_only.reset(token)


@contextmanager
def trajectory(trajectory_id: str) -> Iterator[Trajectory]:
    """Calls made inside the block belong to one screen-operation task; the operator's loop
    says which step with :func:`set_trajectory_step`."""
    t = Trajectory(trajectory_id)
    token = _trajectory.set(t)
    try:
        yield t
    finally:
        _trajectory.reset(token)


def set_trajectory_step(step: int) -> None:
    t = _trajectory.get()
    if t is not None:
        t.step = max(0, int(step))


def current_turn() -> Turn | None:
    return _turn.get()


def next_call() -> int:
    """One more model call in the current turn; its number within the turn (0 outside one)."""
    t = _turn.get()
    if t is None:
        return 0
    t.calls += 1
    return t.calls


__all__ = [
    "RUNS",
    "USER_AGENT",
    "Trajectory",
    "Turn",
    "begin_turn",
    "client_headers",
    "conversation",
    "current_conversation",
    "current_turn",
    "end_turn",
    "enter",
    "leave",
    "new_fallback",
    "next_call",
    "run",
    "run_of",
    "session_id",
    "set_trajectory_step",
    "trajectory",
    "turn",
]
