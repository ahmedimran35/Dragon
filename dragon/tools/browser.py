"""Browser tool. The page is summarised for the model as readable text plus a numbered list of
interactive elements; actions refer to those numbers.

Where the page renders is a :class:`~dragon.tools.browser_backends.BrowserBackend`: a
Playwright Chromium on the computer (``pip install "dragon[browser]" && playwright install
chromium``), with a profile kept under the workspace so logins survive a restart.

Every bot gets its own browser: its own persistent profile, its own pages and its own
downloads, so cookies and signed-in sessions do not leak between bots. The chief (bot id
``default``) keeps the historic location ``<workspace>/browser-profile`` — its existing
logins keep working — while any other bot uses
``<workspace>/bots/<bot_id>/browser-profile``. A run outside any bot turn (a channel
login, the CLI) sees the default bot and therefore uses the chief's profile; that is
intended. One Playwright context and one lock per bot: a bot's own browser actions
serialise against each other while different bots browse in parallel, each in its own
context.

What the browser shows is also shown to the user: after every action a JPEG frame of the
viewport goes to ``on_frame`` (the app turns that into a live browser card), and the user can
take over — click, type, open a URL — through :meth:`Browser.user_action`. That is how a
login happens: the agent stops at the form, the user signs in, the agent carries on with
the page as the user left it.
"""

from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from pydantic import PrivateAttr

from dragon.agent.holds import HAND_OVER_TIMEOUT_S, took_over_note
from dragon.bots import BOT_ID_RE, DEFAULT_BOT_ID, running_bot_id
from dragon.logger import logger
from dragon.schema import RiskLevel, ToolResult
from dragon.tools.base import BaseTool, CallAssessment
from dragon.tools.browser_backends import (
    PROFILES,
    BrowserBackend,
    BrowserProfile,
    PlaywrightBackend,
    profile_named,
)
from dragon.tools.web import _is_private_host, host_of

# the default (desktop) viewport; the frame the user sees is whatever the backend's profile is
VIEWPORT = PROFILES["desktop"].viewport

# what a fetch hands back to the model at most
FETCH_MAX_HOPS = 5
FETCH_MAX_CHARS = 20_000


def _safe_bot_id(bot_id: str) -> str:
    """A bot id that is safe as one path component of the workspace.

    The roster only hands out ``default`` and ``b_`` + 8 hex digits; anything else is
    refused rather than risk two bots sharing (or escaping into) one directory.
    """
    bot = str(bot_id or "").strip()
    if bot == DEFAULT_BOT_ID or BOT_ID_RE.fullmatch(bot):
        return bot
    raise ValueError(f"not a bot id: {bot_id!r}")


def _redirect_target(result: dict[str, Any], base: str) -> str | None:
    """Where a redirect answer points (absolute), or ``None`` for a final answer."""
    status = int(result.get("status") or 0)
    if status not in (301, 302, 303, 307, 308):
        return None
    headers = {str(k).lower(): str(v) for k, v in (result.get("headers") or {}).items()}
    location = headers.get("location", "").strip()
    if not location:
        return None
    return urljoin(str(result.get("url") or base), location)


@dataclass
class BrowserFrame:
    """One picture of the browser, right after something happened."""

    url: str
    title: str
    # a caption for people: "Opened example.com", "Clicked 'Sign in'", "You typed"
    action: str
    jpeg: bytes
    by_user: bool = False
    # the chat this belongs to when known (user actions come from the app, not an agent run)
    thread: str | None = None
    # the backend that rendered it ("playwright")
    backend: str = ""
    width: int = 0
    height: int = 0


_ANNOTATE_JS = """
(maxElements) => {
  const sel = 'a[href], button, input, textarea, select, summary, [role=button], [role=link], [role=tab], [role=menuitem], [onclick], [contenteditable=true]';
  document.querySelectorAll('[data-om-idx]').forEach(e => e.removeAttribute('data-om-idx'));
  const visible = (e) => {
    const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const els = Array.from(document.querySelectorAll(sel)).filter(visible).slice(0, maxElements);
  return els.map((e, i) => {
    e.setAttribute('data-om-idx', String(i));
    const text = (e.innerText || e.value || e.getAttribute('aria-label') || e.getAttribute('placeholder') || e.getAttribute('title') || e.getAttribute('name') || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
    return { i, tag: e.tagName.toLowerCase(), type: e.getAttribute('type') || '', text, href: (e.getAttribute('href') || '').slice(0, 120) };
  });
}
"""

_TEXT_JS = "() => document.body ? document.body.innerText : ''"

_LABEL_JS = """
(i) => {
  const e = document.querySelector('[data-om-idx="' + i + '"]');
  return e ? (e.innerText || e.value || e.getAttribute('aria-label') || e.getAttribute('placeholder') || '').trim() : '';
}
"""

# The accessibility tree of the page as `Screen.nodes`: text, centre and bounds in viewport
# CSS pixels (1:1 with the screenshot), plus flags so the Sentinel can see a password field
# or the words under a click. Same selector and visibility rule as the text summary, so the
# two views of the page name the same elements.
_NODES_JS = """
(maxElements) => {
  const sel = 'a[href], button, input, textarea, select, summary, [role=button], [role=link], [role=tab], [role=menuitem], [onclick], [contenteditable=true]';
  const visible = (e) => {
    const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const els = Array.from(document.querySelectorAll(sel)).filter(visible).slice(0, maxElements);
  return els.map((e) => {
    const r = e.getBoundingClientRect();
    const text = (e.innerText || e.value || e.getAttribute('aria-label') || e.getAttribute('placeholder') || e.getAttribute('title') || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
    const tag = e.tagName.toLowerCase();
    const type = e.getAttribute('type') || '';
    const isInput = tag === 'input';
    // the element's role in the page: fields and text carry words, buttons are clickable
    return {
      class: tag,
      text: text || (type && isInput ? type : ''),
      cx: Math.round(r.left + r.width / 2),
      cy: Math.round(r.top + r.height / 2),
      box: [Math.round(r.left), Math.round(r.top), Math.round(r.left + r.width), Math.round(r.top + r.height)],
      clickable: ['a','button','summary','select'].includes(tag) || (isInput && ['submit','button','reset','image'].includes(type)) || (e.getAttribute('role') || '').startsWith('button') || !!e.getAttribute('onclick') || e.isContentEditable,
      editable: ['input','textarea','select'].includes(tag) || e.isContentEditable,
      password: type === 'password',
      focused: document.activeElement === e,
      checked: e.checked !== undefined ? e.checked : undefined,
      disabled: !!e.disabled,
      selected: e.selected === true || undefined,
    };
  });
}
"""


def playwright_available() -> bool:
    return PlaywrightBackend.available()


class Browser(BaseTool):
    name: str = "browser"
    description: str = (
        "Use the real, visible web browser. It is the default for anything the user would "
        "want to read or watch on the web (a search, news, a weather forecast, a product, a "
        "live page, a site to look at), because the user watches it live in the app and can "
        "take over. It also drives sites end to end: navigate, search, read pages, fill forms, "
        "click, sign in, buy or book, and finish on the page. "
        "Actions: `navigate` (url), `extract` (read current page + numbered interactive elements), "
        "`click` (index), `type` (index, text, submit=true to press Enter), `press` (key, e.g. 'Enter'), "
        "`scroll` (direction up|down), `back`, `wait` (seconds, for a page that is still drawing itself), "
        "`screenshot`, `fetch` (url: GET a URL with the browser's "
        "cookies and return the raw body, a signed-in request without driving the page; method/body "
        "for POST), `profile` (profile: mobile|desktop, or user_agent/width/height: how the browser "
        "presents itself), `close`. After navigate/click/type the tool returns the new page state. "
        "The user watches the browser live in the app and can take over it. Never enter passwords, "
        "one-time codes, CAPTCHAs or payment details yourself: when a page needs a sign-in, a code "
        'or a confirmation only the user can give, call `hand_over` with a short `reason` ("sign in '
        'to Gmail", "enter the code sent by SMS"): the user does it in the browser view, presses '
        "Done, and the tool returns the page as they left it; continue from there. `hand_over` is "
        "for things done on the page; `ask_user` is for an answer in words. If the user takes the "
        "page over themselves, your next action waits until they are done. Leave the browser open "
        "when you finish (no `close` unless asked) so the user can look at or take over the page."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "navigate",
                    "extract",
                    "click",
                    "type",
                    "press",
                    "scroll",
                    "back",
                    "wait",
                    "screenshot",
                    "fetch",
                    "profile",
                    "hand_over",
                    "close",
                ],
            },
            "reason": {
                "type": "string",
                "description": "For hand_over: what the user should do on the page, in their language.",
            },
            "url": {"type": "string"},
            "index": {"type": "integer", "description": "Element number from the last page state."},
            "text": {"type": "string"},
            "submit": {"type": "boolean"},
            "key": {"type": "string"},
            "direction": {"type": "string", "enum": ["up", "down"]},
            "seconds": {"type": "number", "description": "For wait: how long, at most 15."},
            "method": {"type": "string", "description": "For fetch: GET (default) or POST."},
            "body": {"type": "string", "description": "For fetch with POST: the request body."},
            "profile": {"type": "string", "enum": ["mobile", "desktop"]},
            "user_agent": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
        },
        "required": ["action"],
    }
    risk: RiskLevel = RiskLevel.MODERATE
    egress: bool = True

    headless: bool = True
    timeout_ms: int = 30_000
    workspace: Path = Path("./workspace")
    # "auto" | "playwright"
    backend_mode: str = "auto"
    # the starting profile: "mobile" or "desktop" (user agent and viewport)
    default_profile: str = ""
    # receives a BrowserFrame after every action; set by the app
    on_frame: Callable[[BrowserFrame], None] | None = None
    frame_quality: int = 55
    # the holds registry (dragon.agent.holds): the tool waits while the user has the page
    holds: Any = None
    hand_over_timeout: float = HAND_OVER_TIMEOUT_S

    # one browser per bot: backend (Playwright context), lock and notes, keyed by bot id,
    # so two bots working at once never share a context, a profile or each other's state
    _backends: dict[str, Any] = PrivateAttr(default_factory=dict)
    _locks: dict[str, asyncio.Lock] = PrivateAttr(default_factory=dict)
    # what the user did since the model last looked at the page, per bot
    _user_actions: dict[str, list[str]] = PrivateAttr(default_factory=dict)
    # the host of the page last summarised per bot, for the Sentinel's view of the next action
    _last_hosts: dict[str, str | None] = PrivateAttr(default_factory=dict)

    # ------------------------------------------------------------------ lifecycle
    def profile_dir_for(self, bot_id: str | None = None) -> Path:
        """Playwright's persistent profile for one bot: cookies and logins, kept under the
        workspace.

        The chief (``default``) keeps the historic ``<workspace>/browser-profile`` so its
        existing logins keep working; every other bot gets
        ``<workspace>/bots/<bot_id>/browser-profile`` and never sees another bot's
        sessions. ``bot_id=None`` means the running bot, which outside a bot turn
        (channel logins, the CLI) is the chief — intended.
        """
        bot = _safe_bot_id(bot_id or running_bot_id())
        if bot == DEFAULT_BOT_ID:
            return self.workspace / "browser-profile"
        return self.workspace / "bots" / bot / "browser-profile"

    @property
    def profile_dir(self) -> Path:
        """The running bot's persistent profile (see :meth:`profile_dir_for`)."""
        return self.profile_dir_for()

    def screenshots_dir_for(self, bot_id: str | None = None) -> Path:
        """Where the ``screenshot`` action saves: ``<workspace>/screenshots`` for the
        chief, ``<workspace>/bots/<bot_id>/screenshots`` for a staff bot — each bot's
        work stays in its own corner of the workspace."""
        bot = _safe_bot_id(bot_id or running_bot_id())
        if bot == DEFAULT_BOT_ID:
            return self.workspace / "screenshots"
        return self.workspace / "bots" / bot / "screenshots"

    def _pick_backend(self, bot_id: str | None = None) -> BrowserBackend:
        """The backend for one bot's session. A running one is kept until it is closed.

        One backend — one Playwright context on one profile — per bot.
        """
        bot = _safe_bot_id(bot_id or running_bot_id())
        current = self._backends.get(bot)
        if current is not None and current.open:
            return current
        if not playwright_available():
            raise RuntimeError(
                "playwright is not installed. Run: pip install 'dragon[browser]' && playwright install chromium"
            )
        backend: BrowserBackend = PlaywrightBackend(
            self.profile_dir_for(bot),
            headless=self.headless,
            timeout_ms=self.timeout_ms,
            profile=profile_named(self.default_profile or "desktop"),
        )
        self._backends[bot] = backend
        return backend

    @property
    def backend(self) -> BrowserBackend | None:
        """The running bot's backend, if it has one (see :meth:`backend_for`)."""
        return self.backend_for()

    def backend_for(self, bot_id: str | None = None) -> BrowserBackend | None:
        """One bot's backend, if it has one."""
        return self._backends.get(_safe_bot_id(bot_id or running_bot_id()))

    @property
    def backend_kind(self) -> str:
        """Which backend a session would use now: "playwright" or ""."""
        current = self.backend_for()
        if current is not None and current.open:
            return str(current.kind)
        return "playwright" if playwright_available() else ""

    @property
    def lock(self) -> asyncio.Lock:
        """The running bot's browser lock (see :meth:`lock_for`)."""
        return self.lock_for()

    def lock_for(self, bot_id: str | None = None) -> asyncio.Lock:
        """One lock per bot: a bot's browser actions serialise against each other while
        different bots drive their own contexts in parallel. One global lock would stop
        the world for a slow page; per-bot keeps the concurrency as coarse as the
        isolation and no coarser."""
        bot = _safe_bot_id(bot_id or running_bot_id())
        lock = self._locks.get(bot)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[bot] = lock
        return lock

    @property
    def open(self) -> bool:
        """Whether the running bot's browser is open (see :meth:`open_for`)."""
        return self.open_for()

    def open_for(self, bot_id: str | None = None) -> bool:
        """Whether one bot's browser is open."""
        current = self.backend_for(bot_id)
        return current is not None and current.open

    @property
    def viewport(self) -> dict[str, int]:
        current = self.backend_for()
        return current.profile.viewport if current is not None else VIEWPORT

    async def _frame(
        self, backend: BrowserBackend, action: str, by_user: bool = False, thread: str | None = None
    ) -> None:
        if self.on_frame is None:
            return
        try:
            jpeg = await backend.screenshot(self.frame_quality)
            url = await backend.url()
            title = await backend.title()
        except Exception as exc:  # noqa: BLE001
            logger.debug("browser frame: {}", exc)
            return
        if not jpeg:
            return
        try:
            self.on_frame(
                BrowserFrame(
                    url,
                    title,
                    action,
                    jpeg,
                    by_user,
                    thread,
                    backend=backend.kind,
                    width=backend.profile.width,
                    height=backend.profile.height,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("browser frame listener failed: {}", exc)

    async def _label(self, backend: BrowserBackend, index: int) -> str:
        try:
            text = await backend.evaluate(_LABEL_JS, int(index))
        except Exception:  # noqa: BLE001
            return f"[{index}]"
        text = " ".join(str(text or "").split())
        return f"'{text[:40]}'" if text else f"[{index}]"

    async def cleanup(self) -> None:
        """Close every bot's browser: the tool itself is going away."""
        backends = list(self._backends.values())
        self._backends.clear()
        self._user_actions.clear()
        self._last_hosts.clear()
        for backend in backends:
            await backend.close()

    async def _close_bot(self, bot_id: str | None = None) -> None:
        """Close one bot's browser and drop its notes; other bots keep browsing."""
        bot = _safe_bot_id(bot_id or running_bot_id())
        backend = self._backends.pop(bot, None)
        self._user_actions.pop(bot, None)
        self._last_hosts.pop(bot, None)
        if backend is not None:
            await backend.close()

    # ------------------------------------------------------------------ sentinel
    def assess(self, args: dict[str, Any]) -> CallAssessment:
        action = args.get("action", "")
        target = (
            host_of(str(args.get("url", "")))
            if action in ("navigate", "fetch")
            else self._current_host()
        )
        detail = (
            args.get("url")
            or args.get("text")
            or args.get("index")
            or args.get("key")
            or args.get("profile")
            or ""
        )
        if action == "hand_over":
            return CallAssessment(
                risk=RiskLevel.SAFE,
                egress=False,
                summary=f"browser.hand_over {str(args.get('reason') or '')[:120]}".strip(),
            )
        return CallAssessment(
            risk=RiskLevel.MODERATE,
            egress=action not in ("extract", "screenshot", "close", "scroll", "profile"),
            egress_target=target,
            summary=f"browser.{action} {str(detail)[:120]}".strip(),
        )

    def _current_host(self) -> str | None:
        return self._last_hosts.get(running_bot_id())

    def _notes(self, bot_id: str | None = None) -> list[str]:
        """What the user did on one bot's page since the model last looked at it."""
        bot = _safe_bot_id(bot_id or running_bot_id())
        return self._user_actions.setdefault(bot, [])

    # ------------------------------------------------------------------ execution
    async def execute(
        self,
        action: str = "",
        url: str | None = None,
        index: int | None = None,
        text: str | None = None,
        submit: bool = False,
        key: str | None = None,
        direction: str = "down",
        seconds: float | None = None,
        method: str | None = None,
        body: str | None = None,
        profile: str | None = None,
        user_agent: str | None = None,
        width: int | None = None,
        height: int | None = None,
        reason: str | None = None,
        **_: Any,
    ) -> ToolResult:
        if action == "close":
            await self._close_bot()
            return ToolResult(output="Browser closed.")
        if action == "hand_over":
            return await self._hand_over(reason)
        # the user has the page: wait for their Done, then look again before acting
        if self.holds is not None and await self.holds.wait(self.holds.thread(), "browser"):
            self._notes().append("used the page themselves")
        async with self.lock:
            try:
                backend = self._pick_backend()
            except RuntimeError as exc:
                return ToolResult.fail(str(exc))
            try:
                if action == "fetch":
                    return await self._fetch(backend, url, method, body)
                if action == "profile":
                    return await self._profile(backend, profile, user_agent, width, height)
                return await self._act(
                    backend, action, url, index, text, submit, key, direction, seconds
                )
            except Exception as exc:  # noqa: BLE001 – playwright raises many error types
                return ToolResult.fail(
                    f"browser error: {type(exc).__name__}: {str(exc).splitlines()[0][:300]}"
                )

    async def _act(
        self,
        backend: BrowserBackend,
        action: str,
        url: str | None,
        index: int | None,
        text: str | None,
        submit: bool,
        key: str | None,
        direction: str,
        seconds: float | None = None,
    ) -> ToolResult:
        await backend.ensure()
        await backend.set_url_guard(self._url_allowed)
        if action == "navigate":
            if not url:
                return ToolResult.fail(
                    '`url` is required, for example {"action": "navigate", "url": '
                    '"https://duckduckgo.com/?q=London+weather"}'
                )
            if not url.lower().startswith(("http://", "https://")):
                url = "https://" + url
            if not await self._url_allowed(url):
                return ToolResult.fail(f"refusing to navigate to a private or local address: {url}")
            await backend.goto(url)
            final_url = await backend.url()
            if not await self._url_allowed(final_url):
                return ToolResult.fail(
                    "refusing a navigation whose final URL is a private or local address: "
                    f"{final_url}"
                )
            await self._frame(backend, f"Opened {host_of(url) or url}")
            return await self._state(backend, brief=True)
        if action == "extract":
            await self._frame(backend, "Read the page")
            return await self._state(backend, brief=False)
        if action == "click":
            if index is None:
                return ToolResult.fail(
                    "`index` is required: the element number from the last page state "
                    '(action=extract lists them), for example {"action": "click", "index": 3}'
                )
            label = await self._label(backend, int(index))
            await backend.click_element(int(index))
            await backend.settle(self.timeout_ms)
            await self._frame(backend, f"Clicked {label}")
            return await self._state(backend, brief=True)
        if action == "type":
            if index is None or text is None:
                return ToolResult.fail(
                    '`index` and `text` are required, for example {"action": "type", '
                    '"index": 2, "text": "London", "submit": true}'
                )
            label = await self._label(backend, int(index))
            await backend.fill_element(int(index), text)
            if submit:
                await backend.press("Enter")
                await backend.settle(self.timeout_ms)
            await self._frame(backend, f"Typed into {label}" + (" and submitted" if submit else ""))
            return await self._state(backend, brief=True)
        if action == "press":
            await backend.press(key or "Enter")
            await backend.settle(self.timeout_ms)
            await self._frame(backend, f"Pressed {key or 'Enter'}")
            return await self._state(backend, brief=True)
        if action == "scroll":
            step = backend.profile.height * 0.85
            await backend.scroll(-step if direction == "up" else step)
            await self._frame(backend, f"Scrolled {direction}")
            return await self._state(backend, brief=True)
        if action == "back":
            await backend.back()
            await backend.settle(self.timeout_ms)
            await self._frame(backend, "Went back")
            return await self._state(backend, brief=True)
        if action == "wait":
            # a single-page app that draws itself after `load`; capped so a stuck page cannot
            # hold the run
            try:
                pause = float(seconds) if seconds is not None else 2.0
            except (TypeError, ValueError):
                pause = 2.0
            await asyncio.sleep(min(max(pause, 0.5), 15.0))
            await backend.settle(self.timeout_ms)
            await self._frame(backend, "Waited for the page")
            return await self._state(backend, brief=True)
        if action == "screenshot":
            shots = self.screenshots_dir_for()
            shots.mkdir(parents=True, exist_ok=True)
            path = shots / f"{time.strftime('%Y%m%d-%H%M%S')}.jpg"
            path.write_bytes(await backend.screenshot(85))
            await self._frame(backend, "Took a screenshot")
            return ToolResult(output=f"Screenshot saved to {path}", system=str(path))
        return ToolResult.fail(f"unknown action '{action}'")

    async def _url_allowed(self, url: str) -> bool:
        """Whether a browser network request stays on globally routable HTTP(S)."""
        try:
            scheme = urlparse(url).scheme.lower()
        except ValueError:
            return False
        if scheme not in ("http", "https", "ws", "wss"):
            # the browser's own empty page is not a file or a network address
            return url == "about:blank"
        host = host_of(url)
        if not host:
            return False
        return not await asyncio.to_thread(_is_private_host, host)

    async def _fetch(
        self, backend: BrowserBackend, url: str | None, method: str | None, body: str | None
    ) -> ToolResult:
        if not url:
            return ToolResult.fail(
                '`url` is required, for example {"action": "fetch", "url": "https://…"}'
            )
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        # the same guard as web_fetch: the browser's fetch must not reach the machine's own
        # network (loopback, LAN, cloud metadata) on the model's say-so
        host = host_of(url)
        if host is None or await asyncio.to_thread(_is_private_host, host):
            return ToolResult.fail(f"refusing to fetch a private or local address: {url}")
        result = await backend.fetch(url, method=(method or "GET").upper(), body=body)
        # a public page may answer with a redirect into the LAN; each hop gets the same look
        for _ in range(FETCH_MAX_HOPS):
            location = _redirect_target(result, url)
            if location is None:
                break
            next_host = host_of(location)
            if next_host is None or await asyncio.to_thread(_is_private_host, next_host):
                return ToolResult.fail(
                    f"refusing to follow a redirect to a private or local address: {location}"
                )
            url = location
            result = await backend.fetch(url, method="GET")
        text = str(result.get("body") or "")
        ctype = str((result.get("headers") or {}).get("content-type", ""))
        note = ""
        if len(text) > FETCH_MAX_CHARS:
            note = f"\n... [truncated, {len(text)} chars]"
            text = text[:FETCH_MAX_CHARS]
        head = f"HTTP {result.get('status')} {result.get('url') or url}"
        if ctype:
            head += f" ({ctype.split(';')[0].strip()})"
        return ToolResult(output=f"{head}\n\n{text}{note}")

    async def _profile(
        self,
        backend: BrowserBackend,
        profile: str | None,
        user_agent: str | None,
        width: int | None,
        height: int | None,
    ) -> ToolResult:
        prof: BrowserProfile = profile_named(
            profile or "", user_agent, width, height, base=backend.profile
        )
        await backend.set_profile(prof)
        ua = prof.user_agent or "the browser's own"
        return ToolResult(
            output=f"Profile: {prof.name}, {prof.width}×{prof.height}, user agent {ua}."
        )

    # ------------------------------------------------------------------ the user takes over
    async def _hand_over(self, reason: str | None) -> ToolResult:
        """The agent gives the page to the user (contract C1): a hold goes on with the reason,
        the user does their part and presses Done, and the page comes back as they left it."""
        reason = " ".join(str(reason or "").split())
        if not reason:
            return ToolResult.fail("`reason` is required: say what the user should do on the page")
        if self.holds is None:
            return ToolResult.fail(
                "hand_over is not available here; ask the user with `ask_user` to do it and tell "
                "you when it is done"
            )
        thread = self.holds.thread()
        try:
            backend = self._pick_backend()
            await backend.ensure()
            await self._frame(backend, f"Your turn: {reason[:60]}", thread=thread)
        except Exception as exc:  # noqa: BLE001 — the page may not be open yet; the hold still works
            logger.debug("hand_over frame: {}", exc)
        finished = await self.holds.hand_over(
            thread, "browser", reason, timeout=self.hand_over_timeout
        )
        note = took_over_note("browser", finished)
        async with self.lock:
            try:
                backend = self._pick_backend()
                await backend.ensure()
                await self._frame(backend, "You handed the page back" if finished else "Live view")
                state = await self._state(backend, brief=True)
            except Exception as exc:  # noqa: BLE001
                return ToolResult(output=note) if finished else ToolResult.fail(f"{note} ({exc})")
        return ToolResult(output=f"{note}\n\n{state.output}", error=state.error)

    async def user_action(
        self,
        action: str,
        thread: str | None = None,
        *,
        x: float | None = None,
        y: float | None = None,
        text: str | None = None,
        key: str | None = None,
        dy: float | None = None,
        url: str | None = None,
        bot_id: str | None = None,
    ) -> dict[str, Any]:
        """An action by the user from the app. ``x``/``y`` are fractions of the frame.

        It lands on ``bot_id``'s browser — pass the bot of the thread being watched.
        Without a ``bot_id`` it is the running bot's, which outside a run is the chief's;
        that is also where channel logins and the CLI land.

        Not reviewed by the Sentinel: it is the user acting, on their own browser, with
        their own hands. What they did is reported to the model the next time it looks.
        """
        bot = _safe_bot_id(bot_id or running_bot_id())
        async with self.lock_for(bot):
            backend = self._pick_backend(bot)
            await backend.ensure()
            vp = backend.profile.viewport
            if action == "click":
                if x is None or y is None:
                    raise ValueError("click needs x and y")
                px = min(max(float(x), 0.0), 1.0) * vp["width"]
                py = min(max(float(y), 0.0), 1.0) * vp["height"]
                await backend.click_at(px, py)
                await backend.settle(self.timeout_ms)
                caption, note = "You tapped the page", f"clicked at ({int(px)}, {int(py)})"
            elif action == "type":
                if text is None:
                    raise ValueError("type needs text")
                await backend.type_text(text)
                caption, note = "You typed", f"typed {len(text)} characters"
            elif action == "key":
                await backend.press(key or "Enter")
                await backend.settle(self.timeout_ms)
                caption, note = f"You pressed {key or 'Enter'}", f"pressed {key or 'Enter'}"
            elif action == "scroll":
                await backend.scroll(float(dy if dy is not None else 600))
                caption, note = "You scrolled", "scrolled"
            elif action == "back":
                await backend.back()
                await backend.settle(self.timeout_ms)
                caption, note = "You went back", "went back a page"
            elif action == "navigate":
                if not url:
                    raise ValueError("navigate needs a url")
                if not url.lower().startswith(("http://", "https://")):
                    url = "https://" + url
                await backend.goto(url)
                caption, note = f"You opened {host_of(url) or url}", f"opened {url}"
            elif action == "look":
                caption, note = "Live view", ""
            elif action == "take_over":
                # the user has the page from here on (a hold goes on in the service)
                caption, note = "You have the page", ""
            elif action == "handed_back":
                # the take-over sheet closed: the user drove the page themselves
                caption, note = "You handed the page back", "used the page in the app"
            else:
                raise ValueError(f"unknown action '{action}'")
            if note:
                self._notes(bot).append(note)
                logger.info("browser: user {}", note)
            await self._frame(backend, caption, by_user=True, thread=thread)
            return {"url": await backend.url(), "title": await backend.title()}

    async def _state(self, backend: BrowserBackend, brief: bool) -> ToolResult:
        url = await backend.url()
        if not await self._url_allowed(url):
            return ToolResult.fail(
                f"refusing a navigation whose final URL is a private or local address: {url}"
            )
        max_text = 3000 if brief else 9000
        max_elements = 60 if brief else 150
        elements = await backend.evaluate(_ANNOTATE_JS, max_elements) or []
        text = await backend.evaluate(_TEXT_JS)
        text = " ".join(str(text).split()) if text else ""
        if len(text) > max_text:
            text = text[:max_text] + f" ... [truncated, {len(text)} chars]"
        self._last_hosts[running_bot_id()] = host_of(url) if url else None
        lines = []
        notes = self._notes()
        if notes:
            done = "; ".join(notes[-8:])
            notes.clear()
            lines += [
                f"Note: the user took over the browser in the app and {done}. "
                "Continue from the page as it is now; do not redo what they did.",
                "",
            ]
        lines += [
            f"URL: {url}",
            f"Title: {await backend.title()}",
            "",
            "## Page text",
            text,
            "",
            "## Interactive elements",
        ]
        for e in elements:
            desc = (
                f"[{e['i']}] <{e['tag']}{(' type=' + e['type']) if e['type'] else ''}> {e['text']}"
            )
            if e.get("href"):
                desc += f" → {e['href']}"
            lines.append(desc)
        if not elements:
            lines.append("(none)")
        return ToolResult(output="\n".join(lines))

    # ------------------------------------------------------------------ the vision view
    async def visual_screen(self, backend: BrowserBackend, shots_dir: Path) -> Any:
        """The page as a :class:`Screen` for the operator: the screenshot plus the page's
        accessibility tree (``nodes`` with ``box``/``cx``/``cy`` in viewport CSS pixels,
        1:1 with the picture). The JPEG is saved under ``shots_dir`` like the computer's
        ``Screen``, so traces can point at it."""
        from dragon.gui.screen import Screen

        await backend.ensure()
        url = await backend.url()
        title = await backend.title()
        jpeg = await backend.screenshot(self.frame_quality)
        screen = Screen.from_device(
            {
                "app": backend.kind,
                "app_name": title,
                "route": url[:160],
                "width": backend.profile.width,
                "height": backend.profile.height,
                "keyboard": False,
                "mode": "browser",
                "screenshot": base64.b64encode(jpeg).decode(),
            },
            shots_dir=shots_dir,
        )
        raw_nodes = await backend.evaluate(_NODES_JS, 120) or []
        if isinstance(raw_nodes, list):
            screen.nodes = [_clean(node) for node in raw_nodes if isinstance(node, dict)]
        return screen


def _clean(node: dict[str, Any]) -> dict[str, Any]:
    """The page node → the ``Screen.nodes`` shape (``box`` kept for the Sentinel's
    "under the cursor" read)."""
    out: dict[str, Any] = {}
    for key in ("class", "text"):
        if node.get(key):
            out[key] = str(node[key])[:80]
    for key in ("cx", "cy"):
        if node.get(key) is not None:
            try:
                out[key] = int(float(node[key]))
            except (TypeError, ValueError):
                pass
    box = node.get("box")
    if isinstance(box, list) and len(box) == 4:
        try:
            out["box"] = [int(float(v)) for v in box]
        except (TypeError, ValueError):
            pass
    for key in ("clickable", "editable", "password", "focused", "selected", "disabled"):
        if node.get(key):
            out[key] = True
    if "checked" in node and node.get("checked") is not None:
        out["checked"] = bool(node["checked"])
    return out


def _device_error(message: str) -> Exception:
    """A device error, made lazily to avoid importing ``dragon.gui`` at package init
    (``browser`` is imported at the top of ``dragon.tools``, before the GUI loop exists)."""
    from dragon.gui.errors import DeviceError

    return DeviceError(message)


class BrowserLink:
    """The operator's view of one bot's browser: ``screen()`` for a look, ``act()`` for a
    single mouse/keyboard step. It wraps the :class:`Browser` so the per-bot backend, lock,
    holds and frame glue still apply — every call resolves the *running bot's* backend and
    serialises under its lock, exactly as ``Browser.act`` does — and translates the
    operator's actions to :class:`BrowserBackend` primitives in viewport pixels (the page
    is the unit; no screen-space mapping, unlike the computer's hands)."""

    def __init__(self, browser: Browser) -> None:
        self.browser = browser
        # the freshest screenshot per bot: `last_screen` is what the Sentinel and the
        # operator read, and it must be the *running* bot's, not a shared field two bots
        # could race on. Keyed by bot id like `Browser._backends`/`_locks`.
        self._screens: dict[str, Any] = {}

    @property
    def last_screen(self) -> Any:
        return self._screens.get(running_bot_id())

    @last_screen.setter
    def last_screen(self, value: Any) -> None:
        self._screens[running_bot_id()] = value

    def _backend(self) -> BrowserBackend:
        return self.browser._pick_backend()

    def _shots(self) -> Path:
        return self.browser.screenshots_dir_for()

    async def screen(self) -> Any:
        b = self._backend()
        async with self.browser.lock_for():
            self.last_screen = await self.browser.visual_screen(b, self._shots())
        return self.last_screen

    async def act(self, params: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        action = str(params.get("action") or "")
        b = self._backend()
        async with self.browser.lock_for():
            # guard every action, not just `goto`: a click or submit can navigate too, and
            # the guard aborts a hop whose final URL is private or local (same as _act).
            await b.set_url_guard(self.browser._url_allowed)
            # shortcut: the backend exposes a primary click, typing, keys, scroll and goto.
            # right/middle/drag/move have no primitive yet; they refuse rather than mis-click.
            if action == "goto":
                url = str(params.get("url") or "")
                if not url.lower().startswith(("http://", "https://")):
                    url = "https://" + url
                if not await self.browser._url_allowed(url):
                    raise _device_error(
                        f"refusing to navigate to a private or local address: {url}"
                    )
                await b.goto(url)
                final_url = await b.url()
                if not await self.browser._url_allowed(final_url):
                    raise _device_error(
                        "refusing a navigation whose final URL is a private or local address: "
                        f"{final_url}"
                    )
                await b.settle(self.browser.timeout_ms)
            elif action == "click":
                await b.click_at(float(params["x"]), float(params["y"]))
                await b.settle(self.browser.timeout_ms)
            elif action == "double_click":
                await b.click_at(float(params["x"]), float(params["y"]))
                await b.click_at(float(params["x"]), float(params["y"]))
                await b.settle(self.browser.timeout_ms)
            elif action == "right_click":
                raise _device_error(
                    "right click is not supported in the browser yet; left click instead"
                )
            elif action == "middle_click":
                raise _device_error("middle click is not supported in the browser yet")
            elif action == "drag":
                raise _device_error("drag is not supported in the browser yet")
            elif action == "move":
                pass  # the pointer is already where it will click; a move alone changes nothing
            elif action == "scroll":
                dy = params.get("dy")
                await b.scroll(float(dy) if dy is not None else 300)
            elif action == "type":
                await b.type_text(str(params.get("text") or ""))
                if params.get("submit"):
                    await b.press("Enter")
                    await b.settle(self.browser.timeout_ms)
            elif action == "key":
                keys = params.get("keys") or []
                if isinstance(keys, str):
                    keys = [keys]
                for k in keys:
                    await b.press(str(k))
            elif action == "wait":
                seconds = params.get("seconds")
                await asyncio.sleep(float(seconds) if seconds is not None else 1.0)
            else:
                raise _device_error(f"unknown browser action {action!r}")
            try:
                self.last_screen = await self.browser.visual_screen(b, self._shots())
                looked = True
            except Exception:  # noqa: BLE001
                looked = False
        return {"note": "", "looked": looked}

    async def task_event(self, event: str, text: str = "") -> None:
        return None

    async def wait_connected(self, grace: float) -> bool:
        return True


class BrowserAct(BaseTool):
    """One browser action the operator drives (never exposed to the main agent directly)."""

    name: str = "browser_act"
    description: str = "one action on the browser page"
    parameters: dict[str, Any] = {"type": "object", "properties": {"action": {"type": "string"}}}
    risk: RiskLevel = RiskLevel.MODERATE
    egress: bool = True
    reads_private_data: bool = True
    link: BrowserLink | None = None
    gui: Any = None

    def assess(self, args: dict[str, Any]) -> CallAssessment:
        from dragon.tools.surface import num, trusted_node_words

        action = str(args.get("action") or "")
        host = self.link.browser._current_host() if self.link is not None else None
        screen = self.link.last_screen if self.link is not None else None
        label = str(args.get("label") or "").strip()
        shown = f' "{label[:60]}"' if label else ""
        at = ""
        if args.get("x") is not None and args.get("y") is not None:
            at = f" at ({num(args.get('x'))},{num(args.get('y'))})"
        if action in ("click", "double_click", "right_click", "middle_click"):
            summary = f"browser_act: {action}{shown}{at}"
        elif action == "type":
            summary = f'browser_act: type "{str(args.get("text") or "")[:40]}"' + (
                " and press enter" if args.get("submit") else ""
            )
        elif action == "key":
            summary = f"browser_act: press {'+'.join(str(k) for k in args.get('keys') or [])}"
        elif action == "goto":
            summary = f"browser_act: goto {host_of(str(args.get('url') or '')) or '?'}"
        else:
            summary = f"browser_act: {action}{shown}{at}"

        words = list((self.gui.sensitive_words or []) if self.gui is not None else [])
        risk, warnings, egress = RiskLevel.MODERATE, [], action not in ("wait", "move")
        pointed = action in ("click", "double_click", "right_click", "middle_click")
        if pointed:
            point = None
            try:
                if args.get("x") is not None and args.get("y") is not None:
                    point = (float(args["x"]), float(args["y"]))
            except (TypeError, ValueError):
                point = None
            trusted = trusted_node_words(screen, point)
            evidence = " / ".join(part for part in (label, trusted or "") if part)
            if evidence:
                hit = [w for w in words if w.lower() in evidence.lower()]
                if hit:
                    risk = RiskLevel.SENSITIVE
                    warnings.append(f"the words under the cursor say: {', '.join(hit)}")
            if not label:
                warnings.append("a click with no `label`: nothing says what is under the cursor")
        if action == "type" and args.get("submit"):
            risk, egress = RiskLevel.SENSITIVE, True
        if action == "key":
            combo = tuple(str(k).lower() for k in args.get("keys") or [])
            if combo in (("enter",), ("return",)):
                risk, egress = RiskLevel.SENSITIVE, True
        return CallAssessment(
            risk=risk,
            reads_private_data=True,
            egress=egress,
            egress_target=host if egress else None,
            target=host,
            summary=summary,
            warnings=warnings,
        )

    async def execute(self, **params: Any) -> ToolResult:
        assert self.link is not None
        try:
            result = await self.link.act(params)
        except Exception as exc:  # noqa: BLE001 — device errors and page failures alike
            return ToolResult.fail(str(exc))
        note = str(result.get("note") or "")
        if self.link.last_screen is not None and self.link.last_screen.image_path:
            return ToolResult(output=note or "Done", images=[self.link.last_screen.image_path])
        return ToolResult(output=(note or "Done") + " (the page could not be read afterwards)")


class BrowserTask(BaseTool):
    """A whole job on a web page, run step by step by the operator with the browser as its
    screen. Only when a vision-capable model is set: with a text-only model this refuses and
    the agent keeps using the plain `browser` actions."""

    name: str = "browser_task"
    description: str = (
        "Hand a job on a web page to the browser operator: it loads the site, looks at the "
        "page, clicks, types and scrolls step by step until the job is done, then reports "
        "what it found or did. Prefer the plain `browser` actions for a single navigate, "
        "extract or click; use this for a task that needs seeing the page and acting on it. "
        "Give one concrete `goal` with the facts it needs and any `context` you already have. "
        "It never enters passwords or codes, never confirms a payment, and hands the page to "
        "the user for those. Needs a vision-capable model ([gui] model, or the main model)."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "what to achieve on the page, concretely"},
            "context": {
                "type": "string",
                "description": "facts that help: what was found earlier, preferences, constraints",
            },
        },
        "required": ["goal"],
    }
    risk: RiskLevel = RiskLevel.MODERATE
    egress: bool = True
    reads_private_data: bool = True
    link: BrowserLink | None = None
    operator: Any = None
    holds: Any = None

    def assess(self, args: dict[str, Any]) -> CallAssessment:
        goal = str(args.get("goal") or "")
        host = self.link.browser._current_host() if self.link is not None else None
        return CallAssessment(
            risk=RiskLevel.MODERATE,
            reads_private_data=True,
            egress=True,
            egress_target=host,
            target=host,
            summary=f"browser_task: {goal[:80]}",
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from dragon.tools.surface import BROWSER, wait_hold

        goal = str(kwargs.get("goal") or "").strip()
        if not goal:
            return ToolResult.fail("`goal` is required")
        if self.link is None or self.operator is None:
            return ToolResult.fail("the browser operator is not available")
        context = str(kwargs.get("context") or "")
        if await wait_hold(self.holds, BROWSER) and context:
            context = f"{context}\n(the user just used the page themselves; look first)"
        outcome = await self.operator.run(goal, context=context)
        text = outcome.report()
        images = [outcome.last_image] if outcome.last_image else None
        # a run that gave up is a failed tool call, so the main agent falls back to the plain
        # `browser` actions instead of taking a success that never happened. `ask` (a question
        # for the user) and `stopped` (the user's own Stop) are not failures to fall back from.
        if outcome.status in ("abort", "blocked", "failed", "max_steps"):
            return ToolResult.fail(text)
        return ToolResult(output=text, images=images)


__all__ = [
    "VIEWPORT",
    "Browser",
    "BrowserAct",
    "BrowserFrame",
    "BrowserLink",
    "BrowserTask",
    "playwright_available",
]
