# Third-Party Notices

Dragon itself is GPL-3.0-or-later (see [LICENSE](LICENSE)). The upstream project this
runtime derives from is credited in [NOTICE](NOTICE). This file lists the third-party
dependencies the runtime actually installs — the Python package (`pyproject.toml`) and
the web app (`web/package.json`) — and the licenses their maintainers publish. Each
dependency carries its own copyright and license text in its distribution; this list is
informational and does not change those terms.

Versions are the ranges declared in `pyproject.toml` and `web/package.json`; the exact
versions you install may differ.

## Python — runtime (always installed)

| Package | License |
|---|---|
| openai | Apache-2.0 |
| pydantic | MIT |
| httpx | BSD-3-Clause |
| typer | MIT |
| rich | MIT |
| loguru | MIT |
| cryptography | Apache-2.0 OR BSD-3-Clause |
| tenacity | Apache-2.0 |
| ddgs | MIT |
| beautifulsoup4 | MIT |
| html2text | GPL-3.0-or-later |
| mcp | MIT |
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| qrcode | BSD-3-Clause |
| pywebpush | MPL-2.0 |
| python-dateutil | Apache-2.0 OR BSD-3-Clause |
| pillow | MIT-CMU |
| pypdf | BSD-3-Clause |
| zstandard | BSD-3-Clause |
| tzdata (Windows only) | Apache-2.0 |

## Python — optional extras

| Package | Extra | License |
|---|---|---|
| playwright | `browser` | Apache-2.0 |
| mss | `hands` | MIT |
| pyautogui | `hands` | BSD-3-Clause |
| pyperclip | `hands` | BSD-3-Clause |
| pyobjc-framework-Quartz (macOS) | `hands` | MIT |
| pyobjc-framework-ApplicationServices (macOS) | `hands` | MIT |
| lark-oapi | `channels` (Feishu) | MIT |
| dingtalk-stream | `channels` (DingTalk) | MIT |
| wecom-aibot-sdk-python | `channels` (WeCom) | MIT |
| pytest | `dev` | MIT |
| pytest-asyncio | `dev` | Apache-2.0 |
| ruff | `dev` | MIT |
| mypy | `dev` | MIT |
| types-python-dateutil | `dev` | Apache-2.0 |

## Web app (Node 22)

### Runtime dependencies

| Package | License |
|---|---|
| react | MIT |
| react-dom | MIT |
| react-markdown | MIT |
| remark-gfm | MIT |
| lucide-react | ISC |

### Development dependencies

| Package | License |
|---|---|
| vite | MIT |
| vitest | MIT |
| typescript | Apache-2.0 |
| eslint | MIT |
| @eslint/js | MIT |
| eslint-plugin-react-hooks | MIT |
| globals | MIT |
| typescript-eslint | MIT |
| tailwindcss | MIT |
| @tailwindcss/vite | MIT |
| @vitejs/plugin-react | MIT |
| react-test-renderer | MIT |
| @types/react | MIT |
| @types/react-dom | MIT |
| @types/react-test-renderer | MIT |

## Transitive dependencies

Dependencies of the packages above are installed as well; their licenses are whatever
their own distributions declare. `pip show <package>` and `npm ls` list what is actually
installed. Some transitive dependencies are copyleft (notably LGPL components pulled in
by `cryptography`'s ecosystem and GPL components such as `html2text`), which is one
reason Dragon itself is GPL-3.0-or-later.

## Attribution

[NOTICE](NOTICE) covers the upstream derivation and must be kept with any distribution
of this software, as required by the GPL.
