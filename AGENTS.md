# AGENTS.md — working in this repository

Dragon is a **self-hosted, web-only personal agent runtime**. One runtime serves a React
web app over FastAPI on `127.0.0.1:8787`; everything a person owns lives in one data
directory (`~/.dragon`, or `/data` in the container). There is no cloud service, no
accounts, no relay, no sync, no telemetry and no mobile or desktop app — do not add any.

## Brand rules

- The product is **Dragon**. The default agent is **Ember**. The package/CLI is `dragon`,
  environment variables are `DRAGON_*`, the data dir is `~/.dragon`, the Docker image is
  `dragon`, the volume `dragon-data`, the container user `dragon`.
- The visual direction is **Ember & Ash**: warm charcoal surfaces (`#141110`/`#1F1A17`),
  ember-orange primary (`#C2410C` light / `#FB923C` dark), muted gold accent; the light
  theme is parchment/white.
- **Only `NOTICE` may name the upstream project this runtime derives from.** No other file
  — code, comments, docs, tests, config, CI, commit messages — may name it or its org,
  sites or variants of its name. The CI brand-guard job enforces this.
- No screenshots or assets with old branding. Source brand assets live in `assets/brand/`;
  the web app's own copies are `web/public/`.

## Layout

```
dragon/            the Python package (the runtime)
  agent/           the agent loop (one turn: prompt → model → tools → reply)
  llm/             model clients and the provider catalogue (llm/providers.json)
  sentinel/        approvals: policy, gate, grants, audit log
  tools/           tool implementations (files, shell, web, browser, computer, connectors, MCP, ...)
  gui/ computer/   the screen operator and the computer hands (screen/mouse/keyboard)
  server/          FastAPI API, WebSocket, first-run; server/static/ holds the built web app
  memory/ goals/ reminders/ triggers/ calendar/ contacts/ channels/ skills/ vault/ avatar/ coding/
  cli.py config.py app.py
web/               the React + Vite web app; `npm run build` writes into dragon/server/static
config/            config.example.toml (shipped in the wheel)
tests/             pytest suite (no network; a MockLLM stands in for the model)
docs/              the documentation set
assets/brand/      icon, mark, logo, hero and social-card SVGs
scripts/           small maintenance scripts
```

## Commands

```bash
# Python (3.11+)
pip install -e '.[dev]'
ruff check .
ruff format --check .
python -m pytest -q -m "not live"     # `live` tests need DRAGON_LIVE=1 and a real endpoint

# Web (Node 22)
cd web && npm ci && npm run check     # lint + typecheck + tests
cd web && npm run build               # writes dragon/server/static; commit it with the change

# Container
docker build -t dragon . && docker compose config
```

`dragon/server/static` is **tracked**: the wheel ships the web app so `pip install dragon`
works without Node. Rebuild and commit it whenever `web/` changes.

## Conventions

- **Scope.** Web-only, self-hosted, single user. Optional features that remain: browser
  (Playwright), computer hands, channels (Feishu/DingTalk/WeCom/Telegram), coding agents,
  avatar studio, calendar/contacts/email connectors, MCP servers, skills,
  memory/goals/reminders, Sentinel approvals. Everything else is out of scope.
- **Voice.** Plain, specific, human sentences; say what a thing does. No marketing words,
  no exclamation marks, no superlatives, no emoji in the UI.
- **Config.** Every user-facing setting is a key in `config/config.example.toml` with a
  one-line comment, or a `DRAGON_*` variable in `.env.example`. Secrets are `${VAR}`
  references or vault entries — never literal values in examples.
- **The Sentinel is not optional.** New tools declare a risk level and an `assess()`
  summary; sensitive actions must surface as approval cards and land in the audit log.
- **Tests.** No network in tests; the model is a `MockLLM`. New behaviour needs a test.
- **No secrets, ever.** No keys, tokens or private hosts in code, docs, tests or fixtures.
- **Commits.** Conventional Commits (`feat(server): …`, `fix(sentinel): …`) with a DCO
  sign-off (`git commit -s`). No version bumps outside release commits.
- **User-visible changes** get a line under `## [Unreleased]` in `CHANGELOG.md` and, when
  a doc page describes the behaviour, an update to that page.
