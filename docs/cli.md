# The CLI

`dragon` is for setup, admin and backups — day-to-day use happens in the web app. Run
`dragon --help` for the live list and `dragon <command> --help` for the options.

## Everyday commands

| Command | What it does |
|---|---|
| `dragon chat` | Talk to Ember in the terminal (same data, same tools as the web app) |
| `dragon run "…"` | Run one task and exit — scripts, cron, a git hook |
| `dragon serve` | Serve the web app (default `127.0.0.1:8787`) |
| `dragon daemon` | Keep advancing goals and triggers on a timer, no UI |

```bash
dragon run "summarise today's email into workspace/digest.md"
DRAGON_DATA_DIR=~/.dragon-prod dragon serve --port 8790
```

## Admin

| Command | What it does |
|---|---|
| `dragon goals` | `list`, `show`, `add`, `run`, `status`, `delete` |
| `dragon reminders` | `list`, `add`, `cancel` |
| `dragon triggers` | `list`, `add`, `cancel` |
| `dragon memory` | `list`, `add`, `recall`, `forget`, `tidy`, `changes`, `restore`, `clear` |
| `dragon calendar` | `agenda`, `free`, `feeds`, `add`, `remove` |
| `dragon contacts` | `search`, `list`, `add`, `sources`, `add-source`, `remove-source` |
| `dragon skills` | `list`, `show`, `add`, `new`, `remove`, `enable`, `disable` |
| `dragon vault` | `set`, `list`, `delete` — secrets the model never sees |
| `dragon config` | `init`, `show`, `path` |
| `dragon audit` | Read the Sentinel's action log |
| `dragon doctor` | Check the install, config, model, vault and sandbox |
| `dragon channels` | Configure the chat channels |
| `dragon chatgpt` | Authorize a ChatGPT plan as a model source (optional) |

Useful details:

- `dragon audit -n 100` shows more history; `--json` prints the raw entries for scripting.
- `dragon memory recall "…"` shows what a question would bring back — handy for tuning.
- `dragon vault set NAME` prompts for the value without echoing it; reference it from
  config as `{{vault:NAME}}` or in the web app's connection forms.
- `dragon doctor` is the first thing to run when something behaves oddly
  ([troubleshooting.md](troubleshooting.md)).

## Environment

Any command respects `DRAGON_*` variables (see [.env.example](../.env.example)); the ones
used most:

```bash
DRAGON_CONFIG=config/config.toml   # which config file to read
DRAGON_DATA_DIR=~/.dragon          # where the state lives
DRAGON_WORKSPACE=./workspace       # the agent's files
DRAGON_LOG_LEVEL=DEBUG             # more logs
```

## Exit codes and scripting

`dragon run` exits 0 when the task completed and non-zero when it did not, so it drops
into shell scripts and timers cleanly.
