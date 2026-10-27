# Channels

Channels let you talk to Ember from a chat app: **Feishu (Lark)**, **DingTalk**,
**WeCom**, or **Telegram**. Messages arrive as conversations; replies stream back; and
approval cards can be answered from the chat when the web app is not open.

Everything is off until a channel is added. Chat apps are third parties: treat a channel
as a place where *their* servers see the messages you send there.

## Install

```bash
pip install 'dragon[channels]'     # Feishu, DingTalk, WeCom SDKs
# Telegram needs nothing beyond the base install
```

## Set up a channel

Each platform wants a bot or app of its own; you bring its credentials and Dragon
connects out (no public URL needed for the polling/stream style each uses):

| Channel | What you create | What you end up with |
|---|---|---|
| **Feishu / Lark** | an app in the platform's developer console | app id + app secret (`dragon channels login` can walk the scan-to-create flow) |
| **DingTalk** | a stream-mode robot | client id + client secret |
| **WeCom** | a smart robot | token / key pair |
| **Telegram** | a bot via @BotFather | bot token |

Then pair the chat you want to use and check the result:

```bash
dragon channels status          # what is connected and paired
dragon channels test            # sends a test message to the first paired chat
```

Exact fields per platform are asked for interactively (or set in the Connections area of
the web app) and stored in `<data_dir>/app-settings.json` with the secrets in the vault.

## Pairing and approvals

- A chat is **paired** before it counts: Dragon sends a code, you confirm it
  (`dragon channels pending` / `dragon channels approve <code>`). Unpaired chats get
  nothing. `dragon channels deny <code>` refuses one.
- **Sensitive actions still ask.** A channel message that would send email or run a shell
  command produces an approval card — in the web app and in the chat itself.
- Each channel has its own conversation; the memory and workspace are shared with the
  web app because it is the same agent.

## Practical notes

- **Telegram**: group privacy mode means the bot only sees replies and mentions unless
  you turn it off in BotFather.
- **Feishu/Lark**: `dragon channels login --lark` targets the international console;
  without it, 飞书.
- **Rate limits**: the platforms throttle bots; a busy channel slows replies, nothing
  more.
- **Secrets**: the bot tokens belong in the vault, not in the config file or chat.
- Uninstalling: `dragon channels` has no channel → nothing connects out at all.
