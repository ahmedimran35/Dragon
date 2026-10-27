# Skills

A skill is a how-to written down once: a folder with a `SKILL.md` that teaches the agent
a job — triaging an inbox, planning a trip, filing expenses, using some API. The model
reads the skill when the job comes up and follows it, consistently, every time.

Skills use the Agent Skills format: a directory with a `SKILL.md` (name, description,
instructions) plus any supporting files — templates, scripts, reference material.

## Using skills

- The built-in skills ship with the runtime and are always available; yours live in
  `<data_dir>/skills` (or wherever `[skills] dir` points).
- In chat, run one directly: `/trip-plan Kyoto in November`. Otherwise the agent picks a
  skill by itself when its description matches the task.
- `dragon skills list` shows what is loaded; `dragon skills show <name>` prints one.
- Disable what you never use (`[skills] disabled = [...]`) — the model sees a shorter
  list and picks better.

## Writing a skill

```bash
dragon skills new trip-plan        # scaffolds <data_dir>/skills/trip-plan/
```

`SKILL.md` shape:

```markdown
---
name: trip-plan
description: Plan a multi-day trip from the user's notes and calendar. Use when the
  user asks for an itinerary, packing list or travel schedule.
---

# Planning a trip

1. Read the user's dates from the calendar (`calendar_agenda`).
2. Ask at most one clarifying question; make reasonable defaults otherwise.
3. Build a day-by-day plan into `workspace/trips/<destination>.md`.
4. Include travel times, one rainy-day alternative, and a packing list.
```

Authoring advice:

- **Description is the interface.** Say what the skill does *and when to use it*; that is
  what the model matches against.
- **Steps, not prose.** Numbered, concrete, with file names and tool names spelled out.
- **Put reference material in files** (`reference.md`, a template) and have `SKILL.md`
  point at them — the instructions stay short.
- **Keep secrets out.** Skills are plain text the model reads; use `{{vault:NAME}}`
  placeholders or the connectors instead.
- **Reuse over cleverness** — a skill that shells out to a script in the skill folder
  beats twenty steps of prose.

## Replacing a built-in

A folder in your skills dir with the same name as a built-in replaces it — how you
customise "inbox-triage" without touching the package.

## Testing a skill

`dragon run "use the trip-plan skill for Kyoto in November"` and read the output; watch
the audit log (`dragon audit`) to see which tools it reached for. A skill that needs
approvals every run is telling you to narrow what it touches.
