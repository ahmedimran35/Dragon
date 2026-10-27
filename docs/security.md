# Security

Dragon is designed so that the worst it can do is bounded and visible. This page is the
model; [SECURITY.md](../SECURITY.md) is where reports go.

## The token model

There are no accounts. Access to the web app is one shared secret:

- First run generates a token into `<data_dir>/server_token` and prints it **once** as
  part of the URL — `http://host:8787/#token=…` — also shown as a QR code. The fragment
  (`#token=`) is never sent to the server by the browser's URL bar; the app exchanges it
  for a session over the API.
- Set your own with `DRAGON_SERVER_TOKEN` or `server.token` in the config.
- Rotate by deleting `<data_dir>/server_token` (or changing the variable) and restarting.
- `server.auth = false` / `--no-auth` disables all of this — **development on localhost
  only**. On any network it means anyone who can reach the port owns your agent.

Anyone holding the token can act as you: read memory, approve actions, use your model
keys. Treat it like a password.

## The vault

Keys and passwords live in the vault (`<data_dir>/vault`), encrypted with a Fernet key
stored in `<data_dir>/vault.key` or provided as `DRAGON_VAULT_KEY`:

- `dragon vault set NAME` writes a secret; the web app's connection forms do the same.
- Tools accept `{{vault:NAME}}` placeholders in arguments; the runtime resolves them
  immediately before execution — the model never sees the value, only the placeholder.
- The vault key is the master key. Back it up separately; anyone with it plus the data
  directory has your secrets.

## The Sentinel

Every tool call passes the Sentinel before it runs:

| Level | Examples | Default (`mode = "ask"`) |
|---|---|---|
| safe | read a file in the workspace, search the web | runs |
| moderate | write in the workspace, open a browser page | runs |
| sensitive | send email, shell commands, writes outside the workspace | approval card |

- **Modes** — `ask` (default), `strict` (moderate also asks), `auto` (unattended: only
  deny rules stop it — use for `dragon daemon` you fully trust the tasks of).
- **Rules** — `[[sentinel.rules]]` allow/deny/ask patterns on tool arguments.
- **Standing approvals** — approving "this tool for this host" is remembered for the
  session; everything else keeps asking.
- **Taint tracking** — after private data is read (email, memories, files outside the
  workspace), egress is limited to `sentinel.egress_allowlist` until the session ends.
- **Audit log** — every decision is appended to `<data_dir>/audit.jsonl`; `dragon audit`
  reads it. It does not record file contents or message bodies, only what was called,
  against what, and what was decided.

## The sandbox

On Linux with [bubblewrap](https://github.com/containers/bubblewrap) installed,
`[sandbox] mode = "auto"` runs every shell and Python call in its own namespace:

- only the workspace is writable; your home directory is not visible;
- no network unless the command needs it;
- shared directories must be listed explicitly (`share_read_only`, `share`).

`dragon doctor` says whether the sandbox is active. Without bubblewrap, commands still
run with a scrubbed environment — weaker; install bubblewrap on anything but a throwaway
machine.

## Egress: what leaves the machine

Only what you configure:

- model providers you set up (chat, screen operator, image, video),
- connectors (mail, calendar, contacts), search, channels, MCP servers,
- the browser tool to the pages it is told to open.

There is no telemetry, no update check and no analytics. A firewall allowlist is a
reasonable extra layer: the hosts are exactly the endpoints in your config and
`<data_dir>/app-settings.json`.

## Hardening checklist

- [ ] `host = "127.0.0.1"` behind a reverse proxy with HTTPS ([self-hosting.md](self-hosting.md))
- [ ] `auth = true`, token rotated after setup and stored in a password manager
- [ ] bubblewrap installed; `dragon doctor` confirms the sandbox
- [ ] `sentinel.mode = "ask"` (or `strict`), deny rules for anything you never want
- [ ] vault key backed up separately from the data directory
- [ ] runtime runs as an unprivileged user (the Docker image already does: `dragon`)
