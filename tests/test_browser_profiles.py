"""Every bot gets its own browser: profile directory, context, downloads and state.

The roster (:mod:`dragon.bots`) says whose turn it is; the browser tool keys its world by
it. The chief keeps the historic paths so its logins keep working; a staff bot lives under
``<workspace>/bots/<bot_id>/``. No network and no Chromium here: fake backends and path
assertions only."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from dragon.bots import DEFAULT_BOT_ID, current_bot_id, running_bot_id
from dragon.tools.browser import Browser
from dragon.tools.browser_backends import PlaywrightBackend
from tests.test_browser import FakeBackend, tool_with

STAFF = "b_1a2b3c4d"
OTHER = "b_deadbeef"


@contextmanager
def as_bot(bot_id: str):
    """Run a block as one bot's turn, the way the agent loop sets the roster."""
    token = current_bot_id.set(bot_id)
    try:
        yield
    finally:
        current_bot_id.reset(token)


def bot_backend(tool: Browser, bot_id: str) -> FakeBackend:
    """Give one bot an open fake browser of its own."""
    backend = FakeBackend()
    backend._open = True  # type: ignore[attr-defined]
    tool._backends[bot_id] = backend  # type: ignore[assignment]
    return backend


# ----------------------------------------------------------------------------- paths
def test_profile_dir_is_per_bot_and_the_chief_stays_home(tmp_path: Path):
    tool = Browser(workspace=tmp_path)
    # the chief keeps the legacy location: its existing logins must keep working
    assert tool.profile_dir == tmp_path / "browser-profile"
    assert tool.profile_dir_for(DEFAULT_BOT_ID) == tmp_path / "browser-profile"
    # every other bot gets its own directory under bots/<bot_id>/
    assert tool.profile_dir_for(STAFF) == tmp_path / "bots" / STAFF / "browser-profile"
    assert tool.profile_dir_for(OTHER) == tmp_path / "bots" / OTHER / "browser-profile"
    # while a turn runs, the running bot decides
    with as_bot(STAFF):
        assert running_bot_id() == STAFF
        assert tool.profile_dir == tmp_path / "bots" / STAFF / "browser-profile"
    # outside any turn (channel login, CLI) that is the chief — intended
    assert tool.profile_dir == tmp_path / "browser-profile"


def test_a_bot_id_that_is_not_from_the_roster_is_refused(tmp_path: Path):
    tool = Browser(workspace=tmp_path)
    for bad in ("../evil", "b_1a2b3c4d/../..", "b_ZZZZZZZZ", "default2", "b_1"):
        with pytest.raises(ValueError):
            tool.profile_dir_for(bad)
    # an empty id means the running bot, like None
    with as_bot(STAFF):
        assert tool.profile_dir_for("") == tool.profile_dir_for(None)


# ----------------------------------------------------------------------------- downloads
def test_downloads_lands_next_to_each_bots_profile(tmp_path: Path):
    tool = Browser(workspace=tmp_path)
    chief = PlaywrightBackend(tool.profile_dir_for(DEFAULT_BOT_ID))
    staff = PlaywrightBackend(tool.profile_dir_for(STAFF))
    # the chief's downloads stay where they always were
    assert chief.downloads_dir == tmp_path / "downloads"
    # a staff bot's files land in its own corner of the workspace
    assert staff.downloads_dir == tmp_path / "bots" / STAFF / "downloads"


def test_two_bots_get_two_playwright_contexts(tmp_path: Path, monkeypatch):
    """Cookies live in the profile directory Playwright opens: two profiles, two cookie
    jars, two contexts — a bot never sees another bot's signed-in sessions."""
    import dragon.tools.browser as mod

    monkeypatch.setattr(mod, "playwright_available", lambda: True)
    tool = Browser(workspace=tmp_path)
    a = tool._pick_backend(STAFF)
    b = tool._pick_backend(OTHER)
    assert isinstance(a, PlaywrightBackend) and isinstance(b, PlaywrightBackend)
    assert a is not b and a.profile_dir != b.profile_dir
    assert a.downloads_dir != b.downloads_dir

    # one bot keeps its own context across calls while it is open
    class _Page:
        def is_closed(self) -> bool:
            return False

    a._page = _Page()
    assert tool._pick_backend(STAFF) is a


# ----------------------------------------------------------------------------- state
async def test_two_bots_do_not_share_pages_or_notes(tmp_path: Path):
    tool, _ = tool_with(FakeBackend(), tmp_path)  # the chief's browser
    chief = tool.backend_for(DEFAULT_BOT_ID)
    staff = bot_backend(tool, STAFF)

    await tool.execute(action="navigate", url="https://chief.example")
    with as_bot(STAFF):
        res = await tool.execute(action="navigate", url="https://staff.example")
        assert res.ok
    # open pages do not leak: each browser kept its own page
    assert chief.page_url == "https://chief.example"
    assert staff.page_url == "https://staff.example"
    assert tool.open_for(DEFAULT_BOT_ID) and tool.open_for(STAFF)

    # what the user does on one bot's page does not reach another bot's model context
    await tool.user_action("type", "main", text="topsecret")  # the chief's browser
    await tool.user_action("type", "main", text="hi", bot_id=STAFF)
    assert ("type_text", "topsecret") in chief.calls
    assert ("type_text", "hi") in staff.calls
    assert ("type_text", "hi") not in chief.calls

    with as_bot(STAFF):
        out = (await tool.execute(action="extract")).output
    assert "the user took over the browser" in out
    assert "typed 2 characters" in out and "typed 9 characters" not in out
    out = (await tool.execute(action="extract")).output
    assert "typed 9 characters" in out and "typed 2 characters" not in out
    # and the notes are said once, per bot
    out = (await tool.execute(action="extract")).output
    assert "took over" not in out


async def test_close_shuts_one_bots_browser_only(tmp_path: Path):
    tool, _ = tool_with(FakeBackend(), tmp_path)
    chief = tool.backend_for(DEFAULT_BOT_ID)
    staff = bot_backend(tool, STAFF)

    with as_bot(STAFF):
        res = await tool.execute(action="close")
    assert res.ok and not staff.open and tool.open_for(DEFAULT_BOT_ID)

    await tool.cleanup()  # the tool going away closes everyone
    assert not chief.open and not tool.open_for(DEFAULT_BOT_ID)


async def test_screenshots_land_in_the_bots_own_folder(tmp_path: Path):
    tool, _ = tool_with(FakeBackend(), tmp_path)
    bot_backend(tool, STAFF)

    res = await tool.execute(action="screenshot")
    assert res.system and Path(res.system).parent == tmp_path / "screenshots"
    with as_bot(STAFF):
        res = await tool.execute(action="screenshot")
    assert res.system and Path(res.system).parent == tmp_path / "bots" / STAFF / "screenshots"


# ----------------------------------------------------------------------------- concurrency
def test_each_bot_has_its_own_lock(tmp_path: Path):
    """One context per bot and one lock per bot: a bot's actions serialise against each
    other while different bots drive their own browsers in parallel."""
    tool = Browser(workspace=tmp_path)
    assert tool.lock is tool.lock_for(DEFAULT_BOT_ID)
    assert tool.lock_for(STAFF) is tool.lock_for(STAFF)
    assert tool.lock_for(STAFF) is not tool.lock_for(OTHER)
