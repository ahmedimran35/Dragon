# Models and providers

Dragon is bring-your-own-key: it talks straight to whatever OpenAI-compatible endpoint
you point it at. No proxy, no shared account, no allowance.

## The four slots

| Slot | Config | Used for |
|---|---|---|
| chat | `[llm]` | the conversation, planning, most tool calls |
| screen operator | `[gui]` | the vision model that reads screenshots (browser tool, hands) |
| image | `[image]` | pictures in the avatar studio |
| video | `[video]` | clips in the avatar studio |

The chat slot is the only one you must configure; the others fall back to sensible
defaults (the screen operator tries the chat provider's vision model; the avatar studio
tries the chat provider's image/video model, and is simply unavailable if there is none).

## Providers that work

Anything speaking the OpenAI Chat Completions or Responses API:

```toml
[llm]
provider = "openai"                 # "openai" = Chat Completions; "openai_responses" = Responses
model = "deepseek-flash"
base_url = "https://api.deepseek.com"
api_key = "${DEEPSEEK_API_KEY}"
```

Swap in OpenAI (`https://api.openai.com/v1`), OpenRouter (`https://openrouter.ai/api/v1`),
Anthropic's OpenAI-compatible endpoint, Alibaba Bailian, Zhipu, SiliconFlow, Volcengine,
xAI, Gemini — or any gateway of your own. The catalogue `dragon/llm/providers.json` knows
the common ones: set `provider` to a catalogue id (like `bailian`) and the endpoint and
default model come from it; only the key is yours.

Custom endpoints you add in the web app (Connections) are stored in
`<data_dir>/app-settings.json` with their keys in the vault, and override the config file.

## Local models: Ollama / LM Studio / llama.cpp

Nothing leaves your machine:

```toml
[llm]
model = "qwen3:32b"
base_url = "http://127.0.0.1:11434/v1"   # Ollama
api_key = "ollama"                       # any non-empty string; local servers do not check
```

- **Ollama**: `ollama serve && ollama pull qwen3:32b`, base URL `http://127.0.0.1:11434/v1`.
- **LM Studio**: start its local server (default `http://127.0.0.1:1234/v1`).
- **llama.cpp**: `llama-server` with `--port 8080`, base URL `http://127.0.0.1:8080/v1`.

Local models are often weaker at tool calls. Two knobs help:

```toml
tool_mode = "auto"      # falls back to describing tools in the prompt when function
                        # calling is missing or ignored; "prompt" forces that style
vision = "off"          # for text-only local models; pictures are described by file name
```

If the beginning of replies goes missing with a proxy or gateway that inlines thinking
blocks, set `stream = false` — replies arrive complete, just not word by word.

## A ChatGPT plan instead of a key

`dragon chatgpt login` stores an authorization in the vault; then:

```toml
[llm]
provider = "chatgpt"
model = ""               # empty → the plan's default model
```

This covers chat and the hands, not the image/video slots.

## Keys and the vault

Config file keys use `${VAR}` environment references. Keys added through the web app go
into the vault (`dragon vault set NAME` to add one by hand). The model never sees a vault
value: `{{vault:NAME}}` placeholders are resolved immediately before the request.

## Embeddings (memory recall)

Optional: recall by meaning instead of keywords uses any OpenAI-compatible
`/embeddings` endpoint (an Ollama next to a cloud chat model works well):

```toml
[memory]
embeddings = "auto"
embedding_base_url = "http://127.0.0.1:11434/v1"
embedding_model = "qwen3-embedding:0.6b"
```

`auto` uses the chat endpoint when it supports embeddings and falls back to keywords when
it does not. `dragon doctor` tells you which path is active.
