# Bots

Dragon speaks as a bot: a name, a face, a voice, and its own memory. The bot you already
have becomes the default one and keeps everything it knew. You can make more, each with
its own job and personality, and start a chat with any of them.

## What a bot is

A bot is a persona, not a copy of the runtime. Each one has:

- **a name and a face** — the built-in dragon face, or an emoji with a colour. Faces drawn
  in the [avatar studio](avatar.md) land on the default bot in this release;
- **a voice** — tagline, tone (warm, formal, casual, playful, concise), how it shapes its
  answers, and free-text style, all of which go into its system prompt;
- **standing instructions** — what it should always do or never do;
- **its own memories** — what one bot remembers, another does not see. Memories recorded
  outside a chat are shared by all of them.

What a bot is *not*: it does not get its own tools, model, or permissions in this release.
Every bot shares the runtime's browser, computer hands, skills, and Sentinel policy. Only
the persona, the memories, and the chats are separate.

## The roster

The chats sidebar opens with the roster: every bot's face and name, and what it is up to.
A face works while one of its chats is busy, waits when an approval card is pending for
it, and rests otherwise. Tap a bot to start a chat with it.

## Making and editing bots

Open **Bots** from the sidebar rail or the roster's "Manage". There you can make a bot,
give it a name, face, voice and instructions, and rename or forget one. The default bot
cannot be forgotten — it is the one every existing chat speaks as. Forgetting a bot sends
its chats to the default bot.

New chats carry their bot with them: pick who the chat is with when you start it, and the
chat header, greeting and cards use that bot's name and face. Chats made before bots
existed belong to the default bot.

## Approvals and the log

Approval cards name the bot that asked ("Let Scout use Terminal?"), and every line in
`<data_dir>/audit.jsonl` records which bot acted. The Sentinel's rules are still the
runtime's — one policy for all bots.

## Where it lives

Bots are `<data_dir>/bots.json`. Backing up that file (or the whole data directory) keeps
them; see [self-hosting.md](self-hosting.md).
