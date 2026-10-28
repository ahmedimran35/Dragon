# Changelog

All notable changes to Dragon are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are semantic.

## [Unreleased]

- Bots: the agent beside you is now one of a roster. Each bot has its own name, face, tone,
  style and standing instructions, its own memories, its own browser sessions, and its own
  chats — its face and name follow the conversation. A sidebar roster shows each bot's face
  and what it is up to. The bot you already have becomes the default one and keeps
  everything it knew; the persona you set stays put. Bots are managed from the new Bots
  page: make one, give it a face and a voice, rename or forget it. Approval cards name the
  bot that asked, and the audit log records which bot acted.
- The default bot is your chief of staff, marked as such wherever it appears. It runs the
  roster by asking in chat: create a staff bot, edit one, brief it, or remove one (removal
  asks first, and takes its chat with it). Staff bots cannot touch the roster, and the
  chief cannot remove itself. The
  chief keeps as many chats as it likes; each staff bot gets exactly one chat of its own,
  which opens when you tap the bot. Making a bot suggests faces the others do not wear, so
  no two bots look the same.
- The reflector: after a run, a quiet pass reviews what happened (what you asked, which
  tools ran and how it went, what the tasks recorded) and keeps at most a few durable
  lessons in memory: a preference you showed, a fact about a site, something that failed
  and why. Lessons are recalled like any memory when they fit, said once in the chat as
  "Learned", and listed under *What I've learned* on the Memory page where you can
  correct or forget them. One pass at most every ten minutes; `[agent] reflect = false`
  turns it off.
- The chat model card under Connections is easier to get through and better looking: it
  opens with a readiness panel (a tick per thing already set: provider, model, key), then
  the provider, model and key as titled sections with Save and Test right there. The model
  field is a searchable picker (the provider's models, its default first, folded and
  filtered) with "Other model…" for an id typed by hand; the provider tiles show the
  choice with a tick and the provider's note folds to two lines. The hands model, tool
  calling and proxy moved under a "More settings" fold. The provider tiles say their names
  in English only (the Chinese UI keeps the Chinese through the dictionary), and the
  form's boxes are rounder and softer throughout.
- The agent does its web work in the browser by itself: it opens a search engine or the
  site, searches, reads and works the page to the end, with the user watching live in the
  new panel. With the browser on, `web_search`/`web_fetch` are no longer offered to the
  model at all (the browser's own `fetch` covers raw reads) and a call to them recalled
  from earlier in the conversation is turned back to the browser instead of running; with
  it off they are the fallback. The rule is in the system prompt and the three tool
  descriptions, every search and fetch ends with one line pointing at the browser, and a
  browser call with a missing argument is answered with the shape to call.
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
