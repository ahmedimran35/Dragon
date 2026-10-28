# Bots

Dragon speaks as a bot: a name, a face, a voice, and its own memory. The default bot is
your **chief of staff** — it manages the roster and briefs the others. The staff bots each
have their own job, personality, browser and one chat of their own.

## What a bot is

A bot is a persona, not a copy of the runtime. Each one has:

- **a name and a face** — the built-in dragon face, or an emoji with a colour. When you
  make a bot, the app suggests faces the other bots do not wear. Faces drawn in the
  [avatar studio](avatar.md) land on the default bot in this release;
- **a voice** — tagline, tone (warm, formal, casual, playful, concise), how it shapes its
  answers, and free-text style, all of which go into its system prompt;
- **standing instructions** — its brief: what it should always do or never do;
- **its own memories** — what one bot remembers, another does not see. Memories recorded
  outside a chat are shared by all of them;
- **its own browser** — every bot's web sessions live in their own browser profile
  (`<workspace>/bots/<id>/browser-profile`), so a login one bot holds is not one the next
  bot picks up. The chief keeps the original profile, so nothing you are signed into now
  gets signed out.

What a bot is *not*: it does not get its own tools, model, or permissions in this release.
Every bot shares the runtime's tools, computer hands, skills, and Sentinel policy. Only
the persona, the memories, the chats, and the browser are separate.

## The chief of staff

The default bot wears a **Chief of staff** mark wherever it appears. It keeps the chat
system you know — as many chats as you like — and it runs the roster: it can create a
staff bot, edit one, give or change its brief, and remove one, all by asking in chat.
Removing a bot comes to you as an approval card first. A staff bot cannot manage the
roster, and the chief cannot remove itself.

## The roster

The chats sidebar opens with the roster: every bot's face, name and what it is up to. A
face works while one of its chats is busy, waits when an approval card is pending for it,
and rests otherwise.

## Chats

Each staff bot has exactly one chat of its own. Tap a bot in the roster and its chat opens
— made the first time you ask for it, and the same chat every time after. Its chat shows
its face and name. New chats (the chat button, the chats drawer) are chief chats: the
chief has many, staff bots have one.

## Making and editing bots

Open **Bots** from the sidebar rail or the roster's "Manage", or just tell the chief. The
page shows the roster beside the bot you picked: its face, voice and instructions. The
default bot cannot be forgotten — it is the chief. Forgetting a bot hands its chat to the
chief.

## Approvals and the log

Approval cards name the bot that asked ("Let Scout use Terminal?"), and every line in
`<data_dir>/audit.jsonl` records which bot acted. The Sentinel's rules are still the
runtime's — one policy for all bots.

## Where it lives

Bots are `<data_dir>/bots.json`. Backing up that file (or the whole data directory) keeps
them; see [self-hosting.md](self-hosting.md).
