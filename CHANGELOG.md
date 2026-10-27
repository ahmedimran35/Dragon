# Changelog

All notable changes to Dragon are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are semantic.

## [Unreleased]

- The agent now takes website work to the browser by itself: when the job happens on a
  site (searching anything and working through the results, comparing options, reading a
  map or a listing, filling a form, signing in, buying or booking) it opens the `browser`
  tool and finishes on the page, instead of answering from `web_search`/`web_fetch` text.
  The rule is in the system prompt and the three tool descriptions, and every search and
  fetch ends with one line pointing at the browser, where a weak model looks last.
- A watching panel for the agent's browser, on the right of a wide window (the globe in
  the sidebar): the page it is on updates frame by frame as it works, with what it did to
  get there, the trail of pages it looked at, and the same controls as the viewer sheet —
  take the page, click it, type into it, open a URL, hand it back. It opens itself when
  browsing starts. On a phone, tapping a frame in the chat is still the way in. The
  runtime keeps 40 frames per chat in memory now (was 12) so the trail is worth looking
  at.
- The Ideas tab is now the **Tasks** tab. It holds what needs you right now (an approval,
  a question, a goal's proposed plan change, a goal past its date), what Ember suggests
  from what it knows, what it is working on, what is ready for a look, and what was
  resolved. A started task keeps a log of what was done to it — started, run finished,
  tried again, resolved — and the run's end brings it back ready for a look.
- Suggestions come from the model alone: the starter catalogue is gone, `GET /api/tasks`
  and `POST /api/tasks/{id}/start|hide|resolve|retry|reopen` replace `GET /api/ideas`,
  and an existing `ideas.json` becomes the first suggestions in `tasks.json`.
- The `desktop` hands backend is gone with the desktop app: `settings.hands.backend` now
  accepts `auto`, `pyautogui` or `xdotool`, and an existing `desktop` value degrades to
  `auto` (pyautogui when installed, else xdotool on X11).

## [0.1.0]

Dragon: first release of the self-hosted, web-only agent runtime.

- `dragon serve` serves the React web app and the API on `127.0.0.1:8787`, behind one
  access token generated on first run (or `DRAGON_SERVER_TOKEN`).
- The agent (Ember) with tool calls, goals, reminders, triggers and long-term memory.
- The Sentinel: risk-graded tool calls, approval cards, rules, taint tracking and an
  audit log (`dragon audit`).
- Bring-your-own-model: any OpenAI-compatible endpoint, the `dragon/llm/providers.json`
  catalogue, custom endpoints from the web UI, four model slots (chat, screen operator,
  image, video).
- Optional browser tool (Playwright) and computer hands (screen/mouse/keyboard).
- Channels (Feishu, DingTalk, WeCom, Telegram), connectors (email, calendar, contacts,
  web search), MCP servers, skills, avatar studio and coding-agent tasks.
- CLI for setup, admin and backups: `dragon chat | run | serve | daemon | goals |
  reminders | triggers | memory | calendar | contacts | skills | vault | config | audit |
  doctor | channels | chatgpt`.
- Docker and Docker Compose deployment with the `dragon-data` volume.

[Unreleased]: https://github.com/<your-org>/dragon/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/<your-org>/dragon/releases/tag/v0.1.0
