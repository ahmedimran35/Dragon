# Troubleshooting

First move, always: `dragon doctor` — it checks the config, the model connection, the
vault, the sandbox and the data directory, and names what is wrong. Second:
`DRAGON_LOG_LEVEL=DEBUG dragon serve` for full logs.

## Access and the token

**I lost the `#token=…` link.** The token is in `<data_dir>/server_token`:

```bash
cat ~/.dragon/server_token          # or: docker exec -it <container> cat /data/server_token
```

Then open `http://127.0.0.1:8787/#token=<the value>`. To rotate: stop Dragon, delete the
file, start again — a fresh token is printed once.

**"Connection refused" on 127.0.0.1:8787.** Dragon is not running, or the port differs —
check `DRAGON_SERVER_PORT` and `server.port`. Inside Docker the container listens on
8787; the mapping is what `docker compose ps` shows.

**"Port already in use".** Something else owns 8787 — stop it or run
`dragon serve --port 8790` / set `DRAGON_SERVER_PORT`.

**It works on the server but not from my phone.** The default bind is `127.0.0.1`; put a
reverse proxy in front and use its HTTPS address ([self-hosting.md](self-hosting.md)).

## Models

**401 / 403 from the provider.** The key is wrong or belongs to a different endpoint.
Double-check the key in the vault or `.env`; `curl $BASE_URL/models -H "Authorization: Bearer $KEY"`
is a quick test. Remember OpenAI-compatible endpoints usually want the `/v1` suffix in
`base_url`.

**A local model (Ollama / LM Studio) connects but never calls tools.** Small models are
weak at function calling:

```toml
[llm]
tool_mode = "prompt"     # describe the tools in the prompt instead
vision = "off"           # for text-only models
```

**The first words of replies are missing.** A proxy or gateway is mangling streamed
thinking blocks — set `stream = false` in `[llm]`.

**Pictures attached in chat are ignored.** The model has no vision; `vision = "off"`
makes this explicit and the model gets file names instead. The screen operator is a
separate slot: `[gui]` for browser/hands screenshots.

## Tools, approvals, sandbox

**Approval cards do not appear.** The web app must be connected (WebSocket); reload the
page. `server.approval_timeout` (default one hour) decides how long a card waits before
it counts as denied. In a channel, the card is posted to the paired chat.

**Shell commands are refused or run oddly.** On Linux, check the sandbox:

```bash
dragon doctor          # says whether bubblewrap is active
bwrap --unshare-all --ro-bind / / -- /bin/true   # must succeed
```

Ubuntu 24.04 restricts user namespaces by default; `doctor` and the log say so when it
matters — install the `apparmor` profile for bwrap or adjust the restriction (the CI
workflow in this repo shows the exact steps). Setting `[sandbox] mode = "off"` disables
boxing — understand the trade-off first ([security.md](security.md)).

**The agent writes where it should not.** It cannot without an approval: writes outside
the workspace are `sensitive`. Add directories it may use via `agent.extra_roots`.

## Browser and hands

**"Browser tool is not available".** Install it: `pip install 'dragon[browser]' &&
playwright install chromium` (in Docker: the image built with `WITH_BROWSER=1`), and
make sure `[browser] enabled = true` / `DRAGON_BROWSER_ENABLED=true`.

**Hands do not see the screen (macOS).** Grant Accessibility + Screen Recording to the
terminal app that runs Dragon, then restart it. On Linux/Wayland the hands are limited by
the compositor; an X11 session works best.

## Web app

**Blank page after an upgrade.** The built app is missing or stale —
`cd web && npm ci && npm run build`, or rebuild the Docker image (the image's first stage
builds the web app).

**Files will not attach.** `server.max_upload_mb` (default 25) caps uploads.

## Data and memory

**Memory recall finds nothing by meaning.** Embeddings are off or unreachable —
`[memory] embeddings = "auto"` with a working `/embeddings` endpoint; `doctor` shows the
active path. Keyword recall always works.

**Restored a backup and the vault will not open.** The vault key is missing
(`<data_dir>/vault.key` or `DRAGON_VAULT_KEY`). It is never inside the vault — restore it
from wherever you kept it.

**Permission errors in Docker.** The container runs as uid 1000 and owns `/data`; a
host-mounted directory owned by another uid needs `chown -R 1000:1000` (or match the
ownership to your host user).

## Channels

**Messages ignored.** `dragon channels status` shows connection and pairing; an unpaired
chat gets nothing (`dragon channels pending` / `approve`). Bot tokens live in the vault —
`dragon channels test` sends a message to the first paired chat.

## Still stuck

Collect `dragon doctor` output and `DRAGON_LOG_LEVEL=DEBUG` logs (redact keys and
hostnames), then open an issue — bug reports welcome: the template is in
`.github/ISSUE_TEMPLATE/`.
