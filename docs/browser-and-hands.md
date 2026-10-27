# Browser and hands

Two ways for Ember to drive software that has no API. Both are optional, both are off by
default, and both pass every action through the Sentinel.

## Browser tool (Playwright)

```bash
pip install 'dragon[browser]'
playwright install chromium
```

```toml
[browser]
enabled = true
headless = true
timeout_ms = 30000
```

In Docker: build with `--build-arg WITH_BROWSER=1` (or use the `-browser` image tag) —
Chromium is bundled and the tool is on.

What it does: opens pages, reads text and structure, clicks, types, fills forms,
downloads files into the workspace. The model sees the page as text and a screenshot; the
screen operator's vision model (`[gui]`) describes what is on it when needed.

The usual rules apply: navigation to a new host after private data was read hits the
egress allowlist ([security.md](security.md)), and downloads land in the workspace where
you can see them.

## Computer hands (screen, mouse, keyboard)

For local software with no API — the runtime's own machine only.

```bash
pip install 'dragon[hands]'
```

```toml
[hands]
enabled = true
backend = "auto"        # auto | desktop | pyautogui | xdotool
mode = "auto"           # auto | screen | window (window = one app's window on macOS)
coords = "pixels"       # pixels | norm1000
max_image_width = 1600
settle_s = 0.6
```

What it does: reads the screen (or one window), moves the mouse, clicks, types, scrolls,
uses the clipboard. It works step by step — screenshot, decide, act, screenshot — under
the `[gui]` model's eye and `gui.max_steps` cap.

Platform notes:

- **Linux**: X11 works out of the box (`pyautogui`, or `xdotool` even without the extra
  packages). Wayland needs a portal-capable setup; expect to use `xdotool` on X11 sessions.
- **macOS**: grant Accessibility and Screen Recording to your terminal; `window` mode
  drives one app's window and leaves your own mouse alone.

## Approvals and limits

- Hands actions are `moderate`/`sensitive` per call — typing a command is more dangerous
  than scrolling. In `mode = "ask"` you will approve the risky ones.
- `gui.device_timeout_s` bounds how long a single action may take;
  `gui.reconnect_grace_s` what happens when the session drops mid-task.
- `always_ask_tools = ["shell"]`-style rules apply here too — you can force every hands
  action to ask.
- Anything the hands type into a terminal is a shell call wherever it lands; the audit
  log records the action, not the pixels.

## Tips

- Give the agent a screenshot-worthy starting point: "open the invoices folder in the
  file manager" beats "find the invoice".
- `coords = "norm1000"` is more robust across resolutions; `pixels` is more precise for
  a fixed setup.
- The browser tool is usually better than hands for anything that *is* a website.
