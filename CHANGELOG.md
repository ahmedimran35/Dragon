# Changelog

All notable changes to Dragon are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are semantic.

## [Unreleased]

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

[Unreleased]: https://github.com/dragon/Dragon/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dragon/Dragon/releases/tag/v0.1.0
