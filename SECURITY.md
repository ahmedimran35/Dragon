# Security Policy

## Supported versions

The `main` branch and the latest release receive security fixes. Older releases are
not patched; update before reporting something that may already be fixed.

| Version | Supported |
|---|---|
| latest release | ✅ |
| `main` | ✅ |
| older releases | ❌ |

## Reporting a vulnerability

Report **privately**, not in a public issue:

- GitHub **private vulnerability reporting** on the repository (Security → Report a
  vulnerability), or
- email the maintainers listed on the repository's profile.

Include what you did, what you expected, what happened instead, and the impact you see.
Please give us a reasonable time to fix and release before any public disclosure. A way
past the Sentinel, a leaked secret, an authentication bypass or an SSRF counts — thank
you for those.

## What the runtime touches

Dragon is self-hosted and single-user. On the machine that runs it, it touches:

- **Your keys** — stored encrypted in the local vault (`<data_dir>/vault`, key in
  `<data_dir>/vault.key` or `DRAGON_VAULT_KEY`), sent only to the model providers,
  channels, connectors and MCP servers **you** configure. Nothing is sent anywhere else;
  there is no telemetry, no update check and no analytics.
- **Your workspace** — the agent's files (`./workspace` by default), plus any
  `extra_roots` you allow. Reads outside count as private data (taint tracking); writes
  outside ask for approval.
- **Your network** — only when you configure a provider, connector, channel or MCP
  server, and only to those hosts. The Sentinel's egress allowlist narrows this further
  once private data has been read.
- **Shell and code execution** — on Linux, sandboxed with bubblewrap when available:
  only the workspace is writable and there is no network unless needed.

## The token model

There are **no accounts**. Access to the web app is one shared access token:

- On first run a token is generated into `<data_dir>/server_token` and printed **once**
  as part of the URL (`http://host:8787/#token=…`), which is also shown as a QR code.
- You can set your own with `DRAGON_SERVER_TOKEN` (or `server.token` in the config).
- Rotate by deleting `<data_dir>/server_token` (or changing the variable) and restarting.
- `--no-auth` disables the token entirely. It is for development on localhost only —
  never put a `--no-auth` instance on a network.

Anyone holding the token has full access to the agent and its approvals, so treat it
like a password: keep the server on `127.0.0.1` behind a reverse proxy with HTTPS
([docs/self-hosting.md](docs/self-hosting.md)) and do not paste the tokened link into
places you do not control.

## The Sentinel

Every tool call passes the Sentinel before it runs:

- **Risk levels** — `safe`, `moderate`, `sensitive`; the mode (`ask` / `strict` / `auto`)
  decides what needs an approval card in the web app.
- **Rules** — allow/deny/ask rules on tool arguments (`sentinel.rules` in the config).
- **Taint tracking** — after private data is read, egress is limited to the allowlist.
- **Audit log** — every decision is appended to `<data_dir>/audit.jsonl`
  (`dragon audit` reads it).

The Sentinel is a safety net, not a sandbox substitute: run Dragon as an unprivileged
user, keep `auth = true`, and review approvals. Details in [docs/security.md](docs/security.md).
