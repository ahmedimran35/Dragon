# Architecture

Dragon is one Python package plus one web app. No services to run, no queues, no
database server — state is files (and a little SQLite) in the data directory.

## One turn

What happens when you send a message:

```
you ─► web app (React) ─► FastAPI  /api/*  /ws
                            │
                            ▼
                     the agent loop (dragon/agent)
                            │
        ┌───────────────────┼───────────────────────┐
        ▼                   ▼                       ▼
  build the prompt    call the [llm] model     parse the reply
  (system prompt,     (OpenAI-compatible,      (text, or tool calls)
   memory, goals,      streaming)                  │
   skills, history)                                ▼
                                          Sentinel (dragon/sentinel)
                                          risk · rules · taint · audit
                                                │         │
                                          approved        refused / asks you
                                                ▼
                                          the tool runs
                              (files · shell · web · browser · hands ·
                               connectors · channels · MCP · skills)
                                                │
                                                ▼
                              results go back to the model ─► (loop until
                              the reply is done or max_steps is reached)
                                                │
                                                ▼
                              reply + approval cards ─► web app
```

One "turn" may contain many model calls and tool calls; `agent.max_steps` caps them.
Streaming text reaches the browser as it is generated over the WebSocket; approval
cards arrive the same way and block the loop until answered (`server.approval_timeout`
decides the default answer).

## The module map

| Path | What lives there |
|---|---|
| `dragon/agent/` | the loop: prompt assembly, tool execution, holds (approvals) |
| `dragon/bots/` | the bots: names, faces, personas, and which one a chat speaks as |
| `dragon/llm/` | model clients (Chat Completions, Responses, catalogue ids), sessions, the provider catalogue `providers.json` |
| `dragon/sentinel/` | policy (risk levels, rules), the gate, standing grants, the audit log |
| `dragon/tools/` | every tool the agent can call — `base.py` defines what a tool is |
| `dragon/gui/`, `dragon/computer/` | the screen operator and the computer hands |
| `dragon/server/` | FastAPI app, WebSocket events, first run, connections; `server/static/` is the built web app |
| `dragon/memory/` `goals/` `reminders/` `triggers/` | the proactive parts |
| `dragon/calendar/` `contacts/` `channels/` `coding/` `avatar/` | connectors and extras |
| `dragon/skills/` `vault/` | skills loading; secret storage |
| `dragon/cli.py` `config.py` `app.py` | the CLI, settings, the shared app state |
| `web/` | the React + Vite web app (`npm run build` → `dragon/server/static`) |
| `tests/` | pytest suite with a `MockLLM`; no network |

## Serving model

- `dragon serve` starts uvicorn on `127.0.0.1:8787` (configurable), mounts the API under
  `/api`, the WebSocket under `/ws`, and the built SPA at `/`.
- The SPA is static files; the token lives in the URL fragment and is exchanged for a
  session over the API ([security.md](security.md)).
- Everything the UI can do, the CLI can do — the CLI calls the same code paths.

## State

All of it is under `<data_dir>`:

```
~/.dragon/
  app-settings.json    what the web app configured (connections, custom endpoints)
  bots.json            the bots: names, faces and personas
  audit.jsonl          the Sentinel's log
  server_token         the access token (generated on first run)
  vault/ vault.key     encrypted secrets and their key
  memory/ goals/ reminders/ triggers/      as the names say
  sessions/            conversations
  skills/              your skills
  workspace/           the agent's files (unless DRAGON_WORKSPACE points elsewhere)
```

Backing this directory up is backing Dragon up ([self-hosting.md](self-hosting.md)).

## Design rules worth knowing

- **The Sentinel is in the path of every tool call** — there is no bypass, and the audit
  log is append-only.
- **The model is a swappable client** — anything OpenAI-compatible; the prompts and tools
  do not change when the provider does.
- **Optional features are off until enabled** — browser, hands, channels, connectors,
  MCP; the runtime does nothing over the network you did not configure.
- **The web app is the product surface** — the CLI stays for setup, admin and backups.
