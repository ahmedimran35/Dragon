# Configuration

Every key is documented in [config/config.example.toml](../config/config.example.toml) —
that file is the reference. This page explains where settings live and how they combine.

## Where settings come from

In order of precedence (later wins):

1. **Built-in defaults** — a working setup with no files at all.
2. **The config file** — the first of these that exists: `DRAGON_CONFIG` if set,
   `config/config.toml`, `~/.dragon/config.toml`.
3. **Environment variables** — `DRAGON_*` (see [.env.example](../.env.example)); Docker
   users put them in `.env`, which docker-compose passes through.

Check what Dragon actually loaded with `dragon config show`, and where from with
`dragon config path`. `dragon config init` writes a starter config for you.

## Secrets

Never put keys in the config file. Two safe options:

- **Environment**: `api_key = "${DEEPSEEK_API_KEY}"` — string values expand `${VAR}` and
  `${VAR:-default}`.
- **Vault**: `dragon vault set EMAIL_PASSWORD` stores the value encrypted in
  `<data_dir>/vault`; tools and connectors accept `{{vault:NAME}}` placeholders which are
  resolved just before use — the model never sees the value.

## The sections

| Section | What it sets |
|---|---|
| (top level) | `data_dir`, `log_level` |
| `[agent]` | the agent's name (Ember), step cap, workspace, language, context size |
| `[llm]` | the chat model: provider, model, endpoint, key, streaming, tool mode |
| `[gui]` | the screen operator's vision model (used by browser and hands) |
| `[image]` / `[video]` | the avatar studio's picture and clip providers |
| `[sentinel]` | approval mode, per-tool rules, egress allowlist, taint tracking |
| `[memory]` | what is remembered and how it is recalled (keywords or embeddings) |
| `[connectors]` | email, calendar, contacts, web search |
| `[triggers]` | mail poll interval, webhook throttling |
| `[skills]` | skills on/off and where your own live |
| `[sandbox]` | bubblewrap sandboxing of shell and Python (Linux) |
| `[browser]` | the browser tool (Playwright) |
| `[hands]` | screen/mouse/keyboard on the machine the runtime runs on |
| `[mcp]` | MCP servers (`[[mcp.servers]]` tables) |
| `[server]` | host, port, auth, token, upload limit |

## Things people change first

```toml
[agent]
name = "Ember"
max_steps = 30

[llm]
model = "qwen3:32b"
base_url = "http://127.0.0.1:11434/v1"
api_key = "ollama"

[sentinel]
mode = "ask"                 # "strict" to be asked about more, "auto" for unattended runs

[server]
host = "127.0.0.1"           # behind a reverse proxy, keep this
```

## Applying changes

Edit the file and restart (`docker compose restart`, or Ctrl-C and `dragon serve` again).
Settings read per request from the web app (Connections, custom endpoints) apply
immediately and live in `<data_dir>/app-settings.json`.
