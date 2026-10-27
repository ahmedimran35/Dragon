# Contributing to Dragon

Thanks for helping. Dragon is a self-hosted, web-only personal agent runtime: one Python
package, one web app, one data directory. Keep it that way — no cloud services, no
accounts, no mobile or desktop shells.

## Development setup

You need **Python 3.11+** and **Node 22** (web app only). Docker is optional.

```bash
git clone https://github.com/dragon/Dragon && cd Dragon
pip install -e '.[dev]'            # the runtime + dev tools
pip install -e '.[browser,hands]'  # optional: Playwright, screen/mouse/keyboard
cd web && npm ci && cd ..
```

Run everything from the repository root. The data directory defaults to `~/.dragon`;
point a development instance elsewhere with `DRAGON_DATA_DIR=./.dev-data dragon serve`.

## Checks

```bash
# Python
ruff check .
ruff format --check .
python -m pytest -q -m "not live"

# Web
cd web && npm run check            # eslint + tsc + vitest
cd web && npm run build            # writes dragon/server/static; commit it with the change

# Brand guard (what CI enforces)
# No old project name in any file except NOTICE — see AGENTS.md, "Brand rules".
```

CI (`.github/workflows/ci.yml`) runs the same three groups: Python, web, and the brand
guard. All must be green before a merge.

## Pull requests

- One change per PR; open an issue first for anything large.
- Conventional Commits (`feat(tools): …`, `fix(sentinel): …`) with a DCO sign-off:
  `git commit -s`.
- New behaviour needs a test. Tests never touch the network — a `MockLLM` stands in for
  the model. Tests that call a real endpoint are marked `live` and need `DRAGON_LIVE=1`.
- User-visible changes get a line under `## [Unreleased]` in `CHANGELOG.md`, past tense,
  concrete, in the right section, and an update to the page under `docs/` that describes
  the behaviour.
- If the web app changed: the build under `dragon/server/static` is committed.
- If the provider catalogue changed: `node scripts/providers-json.mjs --check` passes.
- No secrets, internal hostnames or personal data in the diff. No version bumps outside
  release commits.

## Code style

- **Python**: Ruff (line length 100, target 3.11), type hints on new code, `from __future__
  import annotations`. Mypy is configured in `pyproject.toml`; run it on what you touch.
- **TypeScript**: strict, function components, hooks; Tailwind for styling; the shared
  strings live where the web app keeps them today.
- **Voice**: plain, specific, human sentences; say what a thing does. No marketing words,
  no exclamation marks, no superlatives.
- **Docs**: short and practical; every example must actually run.

## Adding a provider

The catalogue is `dragon/llm/providers.json` — the source of truth the web UI reads.

1. Add an entry: `id`, `name`, `protocol` (`openai` | `openai-responses` | `anthropic` |
   `gemini`), `base_url`, `auth` (`key` | `none` | …), `capabilities` (`chat`, `vision`,
   `image`, `video`), `regions`.
2. That is usually all: any OpenAI-compatible endpoint works through `openai`/`openai`
   with a custom `base_url`, so prefer documenting it in `docs/providers.md` over adding
   a bespoke client. Only add a new `protocol` when the wire format genuinely differs
   (`dragon/llm/`).
3. Run `node scripts/providers-json.mjs --check` and the Python tests.

Users can also add custom endpoints in the web UI (Connections); they are stored in
`<data_dir>/app-settings.json` with keys in the vault and need no catalogue entry.

## Adding a tool

1. Subclass `BaseTool` in `dragon/tools/`: JSON schema for the model, and the safety
   metadata the Sentinel needs — `risk` (`safe` / `moderate` / `sensitive`),
   `reads_private_data`, `egress`, `accepts_secrets`. Override `assess()` when the risk
   depends on the arguments (a write is riskier than a read), and give every call a
   one-line `summary` for the approval card and the audit log.
2. Register it in `dragon/tools/surface.py` so the agent sees it.
3. Wire approvals: anything `sensitive` must surface as an approval card in the web app.
4. Tests: one for the happy path, one for the risky path being asked or denied.

## Legal integrity

Dragon is original work in the spirit of clean-room reimplementation:

- **No decompiled, disassembled or copied upstream code**, in whole or in fragments.
  If you have seen a proprietary source, do not contribute code derived from it.
- **No copied assets** — icons, illustrations, screenshots, sounds, fonts (unless
  licensed), names or slogans. Draw new ones; `assets/brand/` is the reference set.
- **Only `NOTICE`** records the upstream project this runtime derives from; nothing else
  in the repository may name it.
- By contributing, you agree your work is licensed under **GPL-3.0-or-later** and that
  you have the right to submit it (DCO sign-off says exactly this).

## Questions

Open an issue. Security reports go privately — see [SECURITY.md](SECURITY.md).
