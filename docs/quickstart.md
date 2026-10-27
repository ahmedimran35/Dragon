# Quickstart

## Requirements

- **Docker** (recommended), or Python 3.11+
- Node 22 only if you build the web app from source
- A model: an API key for any OpenAI-compatible provider, or a local model server

## Run with Docker

```bash
git clone https://github.com/<your-org>/dragon && cd dragon
cp .env.example .env        # put at least one model key here, e.g. DEEPSEEK_API_KEY=sk-…
docker compose up -d
docker compose logs -f
```

The first start prints the access link once:

```
http://127.0.0.1:8787/#token=1a2b3c…
```

Open it — that is the whole setup. The port is bound to `127.0.0.1` only; to use it from
a phone or another machine, follow [self-hosting.md](self-hosting.md) (reverse proxy + HTTPS).

Your data is in the `dragon-data` volume, the agent's files in `./workspace`.

## Run from source

```bash
pip install -e '.[server,browser]'
dragon serve
```

If `dragon/server/static/` is empty (fresh checkout without the built web app):

```bash
cd web && npm ci && npm run build && cd ..
```

## First things to do

1. **Pick a model.** The first-run page asks for one: paste a provider key, or point at a
   local endpoint — Ollama is `http://127.0.0.1:11434/v1`, LM Studio is
   `http://127.0.0.1:1234/v1`. Any OpenAI-compatible endpoint works; see
   [providers.md](providers.md).
2. **Say hello, then give it a real task.** "Read my notes in ./workspace and make a plan
   for the week" is a good first run — it shows tools and the approval flow.
3. **Check the token.** The link with `#token=…` is the only way in; store it in your
   password manager. To rotate: stop Dragon, delete `<data_dir>/server_token`, start again.
4. **Turn on what you need.** Browser, hands, channels, connectors and MCP servers are
   off until you enable them — each has its own page in this documentation.

## Where things live

| What | Where |
|---|---|
| Settings | `config/config.toml` or `~/.dragon/config.toml` ([configuration.md](configuration.md)) |
| Memory, goals, vault, audit log, sessions | `<data_dir>` (`~/.dragon`, `/data` in Docker) |
| The agent's files | `./workspace` (or `DRAGON_WORKSPACE`) |
| The access token | `<data_dir>/server_token` |
| Secrets (API keys, mail passwords) | the vault — `dragon vault set NAME` |

## Next

- [providers.md](providers.md) — models and endpoints
- [self-hosting.md](self-hosting.md) — HTTPS, backups, upgrades
- [security.md](security.md) — what the Sentinel does and how to harden the install
- [cli.md](cli.md) — admin and backup commands
