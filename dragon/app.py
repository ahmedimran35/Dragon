"""Composition root: wires settings → stores, vault, Sentinel, tools, LLM, agent."""

from __future__ import annotations

import contextlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from dragon import prompts
from dragon.agent import DragonAgent
from dragon.agent.holds import Holds
from dragon.background import spawn
from dragon.calendar import CalendarFeeds
from dragon.computer.link import ComputerLink
from dragon.config import CHATGPT_PROVIDER, PROTOCOLS, LLMSettings, Settings
from dragon.contacts import ContactBook
from dragon.goals import GoalStore
from dragon.gui.operator import AUTO_LANGUAGE, COMPUTER, GuiOperator
from dragon.llm import BaseLLM, catalogue, create_llm
from dragon.llm.catalogue import Provider
from dragon.logger import logger, setup_logging
from dragon.memory import Embedder, MemoryIndex, MemoryStore
from dragon.reminders import ReminderStore
from dragon.sandbox import Sandbox
from dragon.search import WebSearchProvider
from dragon.sentinel import AuditLog, Sentinel
from dragon.skills import SkillLibrary
from dragon.tools import (
    AskUser,
    Browser,
    Calendar,
    Contacts,
    Files,
    Forget,
    Goals,
    MCPManager,
    PythonExecute,
    ReadEmails,
    Recall,
    Remember,
    Reminders,
    SendEmail,
    Shell,
    Skills,
    Terminate,
    ToolCollection,
    Triggers,
    WebFetch,
    WebSearch,
    playwright_available,
)
from dragon.tools.bots_tool import Bots
from dragon.tools.computer import ComputerAct, ComputerScreen, ComputerTask
from dragon.triggers import TriggerStore
from dragon.ui import UI
from dragon.vault import CredentialVault

if TYPE_CHECKING:
    from dragon.server.service import DragonService


class DragonApp:
    def __init__(
        self,
        settings: Settings,
        ui: UI,
        llm: BaseLLM | None = None,
        session_id: str | None = None,
    ):
        self.settings = settings
        self.ui = ui
        # the live DragonService, which points this at itself at construction (the roster
        # tool reaches its bot methods through here); None in a runtime without one
        self.service: DragonService | None = None
        setup_logging(settings.log_level, settings.data_dir / "logs")
        settings.ensure_dirs()
        self.session_id = (
            session_id or datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        )

        self.vault = CredentialVault(settings.vault_file, settings.vault_key_file)
        self.memory = MemoryStore(settings.memory_db) if settings.memory.enabled else None
        self.embedder: Embedder | None = None
        self.attach_embedder()
        self.goals = GoalStore(settings.goals_db)
        self.reminders = ReminderStore(settings.reminders_db)
        self.triggers = TriggerStore(settings.triggers_db)
        self.calendar = CalendarFeeds(
            settings.connectors.calendar, vault=self.vault, cache_file=settings.calendar_cache
        )
        self.contacts = ContactBook(
            settings.connectors.contacts,
            vault=self.vault,
            own_file=settings.contacts_file,
            cache_file=settings.contacts_cache,
        )
        self.skills = SkillLibrary(settings.skills, own_dir=settings.skills_dir)
        self.audit = AuditLog(settings.audit_file, session_id=self.session_id)
        self.sentinel = Sentinel(
            settings.sentinel,
            audit=self.audit,
            ui=ui,
            vault=self.vault,
            persistent_approvals_file=settings.data_dir / "approvals.json",
        )
        self.llm = llm or self.make_llm()
        # Holds: the person takes the browser or the screen over for a while and the tools
        # wait (docs/browser.md). The server routes the cards; the CLI has none.
        self.holds = Holds(emit=getattr(ui, "on_hold", None))
        mcp_servers = list(settings.mcp.servers)
        self.mcp = (
            MCPManager(
                mcp_servers,
                resolve=lambda v: self.vault.resolve(v, strict=False),
                redact=self.vault.redact,
            )
            if mcp_servers
            else None
        )
        # This computer's own screen and hands (docs/every-device.md); the link exists when
        # there is a display to look at, the tools only while [hands] is on.
        self.computer: ComputerLink | None = ComputerLink(
            settings.hands,
            shots_dir=settings.agent.workspace / "screenshots",
            on_event=getattr(ui, "on_hands", None),
        )
        self.tools = self._build_tools()
        self.agent = DragonAgent(
            settings=settings,
            llm=self.llm,
            tools=self.tools,
            sentinel=self.sentinel,
            ui=ui,
            audit=self.audit,
            memory=self.memory,
            goals=self.goals,
            calendar=self.calendar,
            contacts=self.contacts,
            skills=self.skills,
            session_file=settings.data_dir / "sessions" / f"{self.session_id}.json",
        )

    def attach_embedder(self) -> None:
        """(Re)build the embedding client from the current settings and give the memory
        store its index — at start, and again when the model or the embeddings endpoint is
        changed in the app. Vectors already stored are kept per model, so a switch back is
        free."""
        old = self.embedder
        self.embedder = None
        if self.memory is not None and self.settings.memory.embeddings != "off":
            self.embedder = Embedder(
                self.settings.memory, self.settings.llm, api_key=self._embedding_key()
            )
        if self.memory is not None:
            self.memory.index = (
                MemoryIndex(self.memory, self.embedder) if self.embedder is not None else None
            )
        if old is not None:
            with contextlib.suppress(RuntimeError):
                spawn(old.close(), "closing the previous embedder")

    def _embedding_key(self) -> str:
        """The key for the embeddings endpoint, resolved from the vault when it refers
        there; the model's own key when none is set (same endpoint, same key)."""
        m = self.settings.memory
        key = m.embedding_api_key or self.settings.llm.api_key
        if self.vault.has_placeholders(key):
            key = self.vault.resolve(key, strict=False)
            if self.vault.has_placeholders(key):
                key = ""
        return key

    # ------------------------------------------------------------------ llm
    def make_llm(self) -> BaseLLM:
        """The model client. ``llm.api_key`` may be a ``{{vault:NAME}}`` reference (that is
        how a key entered in the app is stored); it is resolved here, for the HTTP client
        only — the model itself never sees it."""
        llm_settings = self.settings.llm
        if self.vault.has_placeholders(llm_settings.api_key):
            key = self.vault.resolve(llm_settings.api_key, strict=False)
            if self.vault.has_placeholders(key):
                logger.warning("llm.api_key refers to a vault secret that is not set: {}", key)
                key = ""
            llm_settings = llm_settings.model_copy(update={"api_key": key})
        return create_llm(llm_settings, data_dir=self.settings.data_dir)

    def chat_entry(self) -> Provider | None:
        """The catalogue entry the chat model is on: the one ``[llm] provider`` names, else
        the one whose host ``base_url`` is. None for the ChatGPT sign-in and a
        host the catalogue does not list (a local server, a gateway)."""
        llm = self.settings.llm
        if llm.provider == CHATGPT_PROVIDER:
            return None
        cat = catalogue.load()
        if llm.provider not in PROTOCOLS:
            return cat.get(llm.provider)
        return cat.by_base_url(llm.base_url)

    def hands_choice(self, default_only: bool = False) -> tuple[str, str]:
        """Where the hands' model comes from and which it is: ``("gui", m)`` for an explicit
        ``[gui] model``; else ``("chat", m)`` — the chat provider's own hands model when it
        is an own provider with vision, the chat model itself on a host the catalogue does
        not know. ``default_only`` answers what it would be without ``[gui]``."""
        gui, llm = self.settings.gui, self.settings.llm
        if gui.model and not default_only:
            return "gui", gui.model
        entry = self.chat_entry()
        if entry is None or entry.has("vision"):
            # an own provider with vision: its hands model; the ChatGPT sign-in reads
            # pictures; a host the catalogue does not list is whatever the person installed
            return "chat", (entry.defaults.get("hands") if entry else "") or llm.model
        return "chat", llm.model

    def gui_model(self, default_only: bool = False) -> str:
        """The model the hands use (contract C4): ``[gui] model`` when set; else what
        :meth:`hands_choice` resolves. ``default_only`` answers what it would be without
        ``[gui]``."""
        return self.hands_choice(default_only)[1]

    def make_gui_llm(self) -> BaseLLM:
        """The model for the GUI operator: ``[gui]`` where set, the main model's settings
        for the rest — so one provider and one key can serve both."""
        gui, llm = self.settings.gui, self.settings.llm
        _, model = self.hands_choice()
        # `[gui] provider` may be a catalogue id, which brings its own endpoint
        gui_base = gui.endpoint
        own_host = bool(gui_base) and gui_base != llm.endpoint
        key = gui.api_key or (llm.api_key if not own_host else "")
        if self.vault.has_placeholders(key):
            key = self.vault.resolve(key, strict=False)
            if self.vault.has_placeholders(key):
                logger.warning("gui.api_key refers to a vault secret that is not set: {}", key)
                key = ""
        merged = LLMSettings(
            provider=gui.provider if gui.model else llm.provider,
            model=model,
            base_url=gui_base or llm.base_url,
            api_key=key,
            tool_mode="native",
            stream=False,
            # grounding wants the model's first choice, not a sample
            temperature=0.0,
            max_tokens=llm.max_tokens,
            timeout=llm.timeout,
            extra_headers=dict(llm.extra_headers) if not own_host else {},
            # the same host is reached the same way: through the chat model's proxy
            proxy=llm.proxy if not own_host else "",
        )
        return create_llm(merged, data_dir=self.settings.data_dir)

    # ------------------------------------------------------------------ tools
    def _build_tools(self) -> ToolCollection:
        s = self.settings
        ws: Path = s.agent.workspace
        self.sandbox = Sandbox(
            s.sandbox,
            workspace=ws,
            extra_roots=list(s.agent.extra_roots),
            data_dir=s.data_dir,
            # a skill's scripts and references are readable from inside the box
            ro_roots=[self.skills.own_dir, self.skills.builtin_dir] if s.skills.enabled else [],
            # and so are the tools the user shares with it (a CLI under ~/.nvm; its login)
            shared=list(s.sandbox.share),
            shared_ro=list(s.sandbox.share_read_only),
        )
        tools = ToolCollection(
            Terminate(),
            AskUser(ui=self.ui),
            Files(workspace=ws, extra_roots=list(s.agent.extra_roots)),
            Shell(workspace=ws, sandbox=self.sandbox),
            PythonExecute(workspace=ws, sandbox=self.sandbox),
            WebSearch(provider=WebSearchProvider(s.connectors.search, vault=self.vault)),
            WebFetch(),
            Goals(store=self.goals),
            Reminders(store=self.reminders),
            Triggers(store=self.triggers, available=self.trigger_kinds),
            # the roster is in every bot's collection on purpose: the tool's own runtime
            # check ("the chief of staff only") is the boundary
            Bots(service=lambda: self.service),
        )
        if self.memory is not None:
            tools.add(
                Remember(store=self.memory), Recall(store=self.memory), Forget(store=self.memory)
            )
        if s.connectors.email.enabled:
            tools.add(
                ReadEmails(settings=s.connectors.email, vault=self.vault),
                SendEmail(settings=s.connectors.email, vault=self.vault, book=self.contacts),
            )
        if s.connectors.calendar.enabled:
            tools.add(Calendar(feeds=self.calendar, workspace=ws))
        if s.connectors.contacts.enabled:
            tools.add(Contacts(book=self.contacts))
        if s.skills.enabled:
            tools.add(Skills(library=self.skills))
        if s.hands.enabled and self.computer is not None:
            tools.add(*self.computer_tools())
        if s.browser.enabled:
            tools.add(self.browser_tool())
        return tools

    def browser_tool(self) -> Browser:
        """The browser: Playwright driving a real browser here."""
        s = self.settings
        tool = Browser(
            headless=s.browser.headless,
            timeout_ms=s.browser.timeout_ms,
            workspace=s.agent.workspace,
            backend_mode=s.browser.backend,
            default_profile=s.browser.profile,
            holds=self.holds,
        )
        if not playwright_available():
            logger.warning(
                "browser.enabled=true but playwright is missing: pip install 'dragon[browser]' "
                "(the browser tool stays off until it is)"
            )
        return tool

    def computer_tools(self) -> list[ComputerScreen | ComputerAct | ComputerTask]:
        """The three tools for this computer's screen, sharing one link and one operator
        (the GUI operator loop, speaking the `computer_use` dialect)."""
        assert self.computer is not None
        gui = self.settings.gui

        async def app_gate(app_id: str, label: str) -> bool:
            # "Let <bot> use <App>?" — the bot the run speaks as when it has one,
            # else the agent's name as the config has it
            from dragon.bots import running_bot

            bot = running_bot()
            dragon = str((bot or {}).get("name") or self.settings.agent.name or "Dragon")
            return await self.sentinel.allow_app(app_id, label, dragon)

        act = ComputerAct(link=self.computer, gui=gui, holds=self.holds, app_gate=app_gate)

        def language() -> str:
            lang = self.settings.agent.language
            return AUTO_LANGUAGE if lang in ("", "auto") else lang

        operator = GuiOperator(
            self.computer,
            gui,
            self.sentinel,
            act,
            self.ui,
            make_llm=self.make_gui_llm,
            language=language,
            traces_dir=self.settings.data_dir / "computer-traces",
            dialect=COMPUTER,
            holds=self.holds,
        )
        self.computer_operator = operator
        return [
            ComputerScreen(link=self.computer, holds=self.holds),
            act,
            ComputerTask(link=self.computer, operator=operator, holds=self.holds),
        ]

    def set_hands_enabled(self, enabled: bool) -> None:
        """Turn this computer's screen tools on or off while running (the switch in the app)."""
        self.settings.hands.enabled = bool(enabled)
        if self.computer is None:
            return
        present = "computer_act" in self.tools
        if enabled and not present:
            self.tools.add(*self.computer_tools())
        elif not enabled and present:
            for name in ("computer_screen", "computer_act", "computer_task"):
                self.tools.remove(name)

    def trigger_kinds(self) -> dict[str, bool]:
        """Which trigger kinds have their connector: mail needs the mailbox, event the
        calendar."""
        s = self.settings
        return {
            "mail": bool(s.connectors.email.enabled and s.connectors.email.imap_host),
            "event": bool(s.connectors.calendar.enabled and s.connectors.calendar.feeds),
            "hook": True,
        }

    async def start(self) -> DragonApp:
        """Connect optional MCP servers. Call once before using the agent."""
        if self.mcp is not None:
            for tool in await self.mcp.connect():
                self.tools.add(tool)
        return self

    async def close(self) -> None:
        await self.tools.cleanup()
        if self.mcp is not None:
            await self.mcp.close()
        await self.llm.close()
        if self.embedder is not None:
            await self.embedder.close()
        if self.memory is not None:
            self.memory.close()
        self.goals.close()
        self.reminders.close()
        self.triggers.close()

    async def __aenter__(self) -> DragonApp:
        return await self.start()

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ high-level ops
    async def run(self, task: str) -> str:
        return await self.agent.run(task)

    async def advance_goal(self, goal_id: str) -> str:
        goal = self.goals.get(goal_id)
        if goal is None:
            raise ValueError(f"no goal {goal_id}")
        if goal.status != "active":
            raise ValueError(f"goal {goal_id} is {goal.status}")
        self.agent.reset()
        return await self.agent.run(
            prompts.ADVANCE_GOAL_PROMPT.format(goal=goal.render()), run="goal"
        )


__all__ = ["DragonApp"]
