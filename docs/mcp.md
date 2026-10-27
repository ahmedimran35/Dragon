# MCP servers

Dragon speaks the Model Context Protocol: any MCP server becomes a set of tools for the
agent, which is usually faster than writing a connector.

## Adding a server

In `config/config.toml`:

```toml
[[mcp.servers]]
name = "filesystem"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "./workspace"]
risk = "moderate"
```

or for a remote/streamable server:

```toml
[[mcp.servers]]
name = "calendar"
url = "http://localhost:8000/mcp"
risk = "sensitive"
reads_private_data = true
```

Restart to pick changes up. `dragon doctor` lists what connected and what failed.

## The fields

| Field | Meaning |
|---|---|
| `name` | how the agent and the audit log call the server |
| `command` + `args` | a local process to start (stdio), **or** |
| `url` | a remote endpoint (streamable HTTP / SSE) |
| `env` | environment for the process; values accept `${VAR}` |
| `risk` | `safe` / `moderate` / `sensitive` — the floor for all its tools |
| `reads_private_data` | its calls may expose email, memory, private files (taint) |
| `egress` | its calls can send data out of the machine |

Keys in a URL or args: use a vault reference, e.g.
`url = "https://mcp.example.com/mcp?key={{vault:MAPS_KEY}}"` — the model never sees it.

## Risk and approvals

MCP tools are ordinary tools to the Sentinel:

- a `risk = "sensitive"` server's calls become approval cards in `mode = "ask"`;
- `[[sentinel.rules]]` can target its tools by name for finer control;
- `reads_private_data = true` engages taint tracking: after such a call, egress narrows
  to the allowlist ([security.md](security.md)).

Pick the lowest honest risk level; over-claiming `safe` is how agents get abused.

## Examples that work well

- **A filesystem server** scoped at `./workspace` (`risk = "moderate"`).
- **A local calendar server** on `http://localhost:8000/mcp` (`risk = "sensitive"`).
- **A hosted maps or search server** with the key in the vault (`risk = "safe"`,
  `egress = true`).

## Troubleshooting

- **Server does not connect** — run the command by hand in a shell; the usual culprits
  are a missing `npx`/node, a wrong working directory or a dead URL.
- **Tools are missing in chat** — the server failed at startup (see `dragon doctor`) or
  its tools are all disabled in the web app's tools list.
- **Duplicate tool names** — two servers exposing the same tool name; rename one.
- **Slow first turn** — starting local servers costs a moment; the first request waits
  for them, later ones do not.
