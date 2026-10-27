"""The providers as the app sees them (contract C11), and the ChatGPT sign-in over HTTP.

Two things live here. :func:`providers_view` is ``GET /api/providers``: the catalogue
(``dragon/llm/providers.json``) with, for each entry, which of the four model slots —
``chat``, ``hands``, ``image``, ``video`` — use it today, the union of what those slots can
do, and for every capability nothing covers the one sentence that names who could, in the
request's language. :class:`ChatGPTSignIn` runs the Codex PKCE flow of
``dragon chatgpt login`` inside the server, so the web console can start it, follow it
and finish it without a terminal: ``POST /api/chatgpt/login`` starts one in the background,
``GET /api/chatgpt/status`` reports the store (never the tokens) and the login under way,
``POST /api/chatgpt/callback`` takes the callback URL a person pasted when the browser could
not reach the runtime's port, ``POST /api/chatgpt/logout`` forgets it all. One implementation
of the flow — :class:`dragon.llm.chatgpt.LoginFlow` — serves the CLI and this.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import httpx

from dragon.background import keep_task
from dragon.config import CHATGPT_PROVIDER, PROTOCOLS, resolve_provider
from dragon.llm import catalogue
from dragon.llm.chatgpt import (
    BUILTIN_MODELS,
    LOGIN_TIMEOUT_S,
    REDIRECT_PORT,
    TOKEN_URL,
    Auth,
    ChatGPTError,
    LoginFlow,
    TokenStore,
)
from dragon.llm.chatgpt import (
    CAPABILITIES as CHATGPT_CAPABILITIES,
)
from dragon.llm.chatgpt_proxy import Usage
from dragon.llm.codex import CodexClient
from dragon.logger import logger

if TYPE_CHECKING:
    from dragon.server.service import DragonService

SLOTS: tuple[str, ...] = ("chat", "hands", "image", "video")


# --------------------------------------------------------------------------- the view
def _slot(provider: str, model: str, protocol: str, source: str) -> dict[str, Any]:
    return {"provider": provider, "model": model, "protocol": protocol, "source": source}


class Providers:
    """``GET /api/providers``: what is configured, what that covers, who could cover the rest."""

    def __init__(self, svc: DragonService):
        self.svc = svc

    # -- helpers
    def account_region(self) -> str:
        return ""

    def _id_for(self, provider: str, base_url: str | None) -> str:
        """The catalogue id a slot means: the id it names, the entry whose host the URL is, else ``custom``."""
        if provider == CHATGPT_PROVIDER:
            return CHATGPT_PROVIDER
        if provider and provider not in PROTOCOLS and catalogue.load().get(provider):
            return provider
        base = (base_url or "").rstrip("/")
        entry = catalogue.load().by_base_url(base)
        return entry.id if entry is not None else "custom"

    def _source(self, pid: str, slot: str) -> str:
        if pid == CHATGPT_PROVIDER:
            return "chatgpt"
        data = getattr(self.svc.connections, "data", {})
        key = "gui" if slot == "hands" else ("llm" if slot == "chat" else slot)
        return "app" if data.get(key) else "config"

    def slots(self) -> dict[str, dict[str, Any] | None]:
        """What each slot uses today, in the order of the Models contract (§3): an explicit
        choice first (``source`` ``app`` or ``config``); else ``hands`` follows the chat
        provider when it sees (``source`` ``chat``); ``image`` and ``video`` are the
        avatar studio's answer to "where do pictures come from" — the chat provider's own
        picture model; ``None`` when nothing draws."""
        s = self.svc.settings
        llm, gui = s.llm, s.gui
        chat_id = self._id_for(llm.provider, llm.endpoint)
        chat_protocol = CHATGPT_PROVIDER if chat_id == CHATGPT_PROVIDER else llm.protocol
        chat_source = self._source(chat_id, "chat")
        out: dict[str, dict[str, Any] | None] = {
            "chat": _slot(chat_id, llm.model, chat_protocol, chat_source),
        }
        where, hands_model = self.svc.app.hands_choice()
        if where == "gui":
            if gui.endpoint is None and gui.provider in PROTOCOLS:
                hands_id = chat_id  # the main model's host, another model there
            else:
                hands_id = self._id_for(gui.provider, gui.endpoint)
            protocol = resolve_provider(gui.provider, gui.base_url)[0]
            out["hands"] = _slot(hands_id, hands_model, protocol, self._source(hands_id, "hands"))
        else:
            out["hands"] = _slot(chat_id, hands_model, chat_protocol, chat_source)
        out["image"] = out["video"] = None
        ep = self.svc.avatar.endpoint()
        if ep is not None:
            image_id = self._id_for(s.image.provider if s.image.configured else "", ep.base_url)
            out["image"] = _slot(
                image_id, ep.image_model, "openai", self._source(image_id, "image")
            )
            if ep.video_model:
                video_id = self._id_for(
                    s.video.provider if s.video.configured else "",
                    ep.video_base_url or ep.base_url,
                )
                out["video"] = _slot(
                    video_id, ep.video_model, "openai", self._source(video_id, "video")
                )
        return out

    def view(self, lang: str = "", region: str = "") -> dict[str, Any]:
        """Contract §3. ``lang`` is ``en``/``zh`` (the agent's language when empty); ``region``
        is ``cn``/``global`` (the account's when empty, else every provider)."""
        lang = lang or self.svc.ui_language()
        region = region if region in ("cn", "global") else self.account_region()
        cat = catalogue.load()
        slots = self.slots()
        token = TokenStore.in_dir(self.svc.data_dir).load()
        chatgpt_signed_in = token is not None

        def using(pid: str) -> list[str]:
            return [name for name in SLOTS if (slot := slots.get(name)) and slot["provider"] == pid]

        caps: set[str] = set()
        for name, slot in slots.items():
            if slot is None:
                continue
            pid = slot["provider"]
            if name == "image":
                caps.add("image")
            elif name == "video":
                caps.add("video")
            elif pid != CHATGPT_PROVIDER and (pid == "custom" or cat.get(pid) is None):
                # the person says what their endpoint does: a named hands model sees
                caps.add("chat")
                if name == "hands" and self.svc.settings.gui.model:
                    caps.add("vision")
            else:
                caps |= cat.capabilities([pid]) & {"chat", "vision"}

        providers: list[dict[str, Any]] = []
        for p in cat.providers:
            entry = p.to_dict()
            configured = using(p.id)
            if p.id == "openai":
                configured = configured + [
                    s for s in using(CHATGPT_PROVIDER) if s not in configured
                ]
            entry["configured"] = configured
            entry["signed_in"] = chatgpt_signed_in if p.id == "openai" else False
            providers.append(entry)

        return {
            "providers": providers,
            "region": region,
            "configured": slots,
            "capabilities": [c for c in catalogue.CAPABILITIES if c in caps],
            "unavailable": {
                c: "" if c in caps else cat.unavailable_sentence(c, region, lang)
                for c in catalogue.CAPABILITIES
            },
            "chatgpt": {
                "signed_in": chatgpt_signed_in,
                "label": token.label if token else "",
                "capabilities": list(CHATGPT_CAPABILITIES),
            },
        }


# --------------------------------------------------------------------------- the sign-in
class ChatGPTSignIn:
    """The Codex PKCE sign-in run by the server, one at a time.

    :meth:`login` binds the callback port (1455 — the one registered with OpenAI) on this
    machine and waits in a background task; the browser lands there when it runs on the
    same machine. When it does not — a runtime on another computer — the person pastes
    the address the browser landed on into :meth:`callback`, the same path as the CLI's
    stdin fallback. A second ``login`` while one is pending returns the pending one.
    """

    def __init__(self, svc: DragonService):
        self.svc = svc
        self.store = TokenStore.in_dir(svc.data_dir)
        self.port = REDIRECT_PORT
        #: the token endpoint and the HTTP client the exchange uses; tests point them at a
        #: mock transport
        self.token_url = TOKEN_URL
        self.http: httpx.AsyncClient | None = None
        self._flow: LoginFlow | None = None
        self._task: asyncio.Task[None] | None = None
        self._paste: asyncio.Future[str | None] | None = None
        self._deadline = 0.0
        self._bound = False
        self._error: str = ""
        self._error_code: str = ""
        self._starting: asyncio.Lock | None = None
        self._usage: Usage | None = None

    @property
    def pending(self) -> bool:
        return self._flow is not None

    def signed_in(self) -> bool:
        return self.store.load() is not None

    # -- login
    async def login(self, timeout: float = LOGIN_TIMEOUT_S) -> dict[str, Any]:
        """Start a sign-in (or report the one under way): the page to open, where the
        callback is expected, how long the server waits."""
        if self._starting is None:
            self._starting = asyncio.Lock()
        async with self._starting:
            if self._flow is not None:
                return self._login_view(self._flow)
            self._error = self._error_code = ""
            flow = LoginFlow(self.store, port=self.port, token_url=self.token_url, http=self.http)
            self._bound = await flow.listen()
            if not self._bound:
                logger.warning(
                    "ChatGPT sign-in: port {} is in use; the callback address must be pasted "
                    "(POST /api/chatgpt/callback)",
                    self.port,
                )
            loop = asyncio.get_running_loop()
            self._flow = flow
            self._paste = loop.create_future()
            self._deadline = time.monotonic() + timeout
            self._task = loop.create_task(self._run(flow, timeout), name="chatgpt-login")
            keep_task(self._task)
            return self._login_view(flow)

    def _login_view(self, flow: LoginFlow) -> dict[str, Any]:
        return {
            "url": flow.url,
            "callback": flow.callback_url,
            "expires_in": max(0, int(self._deadline - time.monotonic())),
            "port_bound": self._bound,
        }

    async def _read_paste(self) -> str | None:
        if self._paste is None:
            return None
        return await self._paste

    async def _run(self, flow: LoginFlow, timeout: float) -> None:
        try:
            result = await flow.wait(timeout, paste=self._read_paste)
            token = await flow.finish(result)
            logger.info("ChatGPT sign-in finished from the app ({})", token.label)
        except ChatGPTError as exc:
            self._error, self._error_code = exc.message, exc.code
            logger.warning("ChatGPT sign-in did not finish: {} ({})", exc.message, exc.code)
        except asyncio.CancelledError:
            self._error, self._error_code = "the sign-in was stopped", "cancelled"
            raise
        except Exception as exc:  # noqa: BLE001 — said to the app, never raised into the loop
            self._error, self._error_code = f"{type(exc).__name__}", "error"
            logger.warning("ChatGPT sign-in failed: {}: {}", type(exc).__name__, exc)
        finally:
            if self._flow is flow:
                self._flow = None
                self._task = None
                self._paste = None
            await flow.close()
            self.svc.bus.publish({"kind": "chatgpt", "chatgpt": self.status()})

    def callback(self, url: str) -> dict[str, Any]:
        """The callback address pasted from the browser. ``state`` must be the pending
        login's; the code is exchanged by the waiting task."""
        flow, paste = self._flow, self._paste
        if flow is None or paste is None:
            raise ChatGPTError("no_login", "no sign-in is waiting; start one first")
        result = LoginFlow._parse_callback(url)
        if not result.code and not result.error:
            raise ChatGPTError("bad_callback", "that is not a callback address (no code in it)")
        if result.state != flow.state:
            raise ChatGPTError("state_mismatch", "the callback's state does not match this login")
        if not paste.done():
            paste.set_result(url.strip())
        return {"ok": True}

    async def cancel(self) -> bool:
        """Stop a pending login; True when there was one."""
        task = self._task
        if task is None:
            return False
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        return True

    # -- status / logout
    def status(self) -> dict[str, Any]:
        """The store without the tokens, the login under way, the last failure."""
        token = self.store.load()
        view: dict[str, Any] = {
            "signed_in": token is not None,
            "label": token.label if token else "",
            "plan": token.plan if token else "",
            "account_id": token.account_id if token else "",
            "expires_at": token.expires_at if token else 0,
            "expires_in": token.expires_in if token else 0,
            "models": list(BUILTIN_MODELS),
            "capabilities": list(CHATGPT_CAPABILITIES),
            "pending": self._flow is not None,
        }
        if self._flow is not None:
            view["url"] = self._flow.url
            view["callback"] = self._flow.callback_url
            view["port_bound"] = self._bound
            view["login_expires_in"] = max(0, int(self._deadline - time.monotonic()))
        elif self._error:
            view["error"] = self._error
            view["error_code"] = self._error_code
        return view

    async def usage(self) -> dict[str, Any]:
        """What is left of the plan's windows, as OpenAI reports it; at most one request a
        minute. ``{signed_in, plan, label, limits | null, error}`` — never raises."""
        if self._usage is None:
            proxy = self.svc.settings.llm.proxy.strip() or None
            auth = Auth(self.store, http=self.http, token_url=self.token_url, proxy=proxy)
            self._usage = Usage(
                auth, CodexClient(auth, http=self.http, proxy=proxy), http=self.http
            )
        return await self._usage.view()

    async def logout(self) -> dict[str, Any]:
        await self.cancel()
        was = self.store.clear()
        if self._usage is not None:
            self._usage = None
        self._error = self._error_code = ""
        self.svc.bus.publish({"kind": "chatgpt", "chatgpt": self.status()})
        return {"ok": True, "was_signed_in": was}

    async def close(self) -> None:
        await self.cancel()


__all__ = ["SLOTS", "ChatGPTSignIn", "Providers"]
