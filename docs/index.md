# Dragon documentation

Dragon is a self-hosted, web-only personal agent runtime. One process — `dragon serve` —
runs the agent (Ember), the tools, and the web app you open at `http://127.0.0.1:8787`.
Everything lives in one data directory (`~/.dragon`, or `/data` in the container).

Start here:

| Page | What it covers |
|---|---|
| [quickstart.md](quickstart.md) | Install, first run, the access-token link |
| [configuration.md](configuration.md) | Config file, `DRAGON_*` variables, precedence |
| [providers.md](providers.md) | Bring-your-own-key, Ollama / LM Studio, custom endpoints |
| [self-hosting.md](self-hosting.md) | Docker, reverse proxy + HTTPS, backup and restore |
| [cli.md](cli.md) | Every `dragon` command |
| [security.md](security.md) | Token model, vault, Sentinel, sandbox, egress |
| [architecture.md](architecture.md) | How one turn works, the module map |
| [avatar.md](avatar.md) | The avatar studio (pictures and clips) |
| [bots.md](bots.md) | Bots: personas, faces, and the roster |
| [browser-and-hands.md](browser-and-hands.md) | Browser automation and computer hands |
| [channels.md](channels.md) | Feishu, DingTalk, WeCom, Telegram |
| [mcp.md](mcp.md) | MCP servers as tools |
| [skills.md](skills.md) | Skills (Agent Skills format) |
| [troubleshooting.md](troubleshooting.md) | When something does not work |

## The shape of the system

```
browser ──► web app (React) ──► FastAPI (127.0.0.1:8787) ──► the agent loop
                                                              │  tools
                                                              ▼
model endpoint (yours) ◄───────────────────── Sentinel ──► files, shell, web,
(OpenAI-compatible, local or remote)                         browser, hands, MCP,
                                                             connectors, channels
```

Three things to know before anything else:

1. **The token is the only key to the app.** First run prints
   `http://127.0.0.1:8787/#token=…` once; the token is also in `<data_dir>/server_token`.
2. **The model is yours.** Bring an API key or point at a local server; Dragon never
   proxies your traffic through anything.
3. **The Sentinel watches every tool call.** Sensitive actions become approval cards in
   the web app and everything lands in `<data_dir>/audit.jsonl`.
