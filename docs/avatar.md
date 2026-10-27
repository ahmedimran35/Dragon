# Avatar studio

The avatar studio draws pictures and clips for the agent: a face for Ember, illustrations
for a story, a short animated clip of the avatar. It uses whatever image/video providers
you configure — the runtime ships no generation service of its own.

## Providers

Two slots, both optional:

```toml
[image]
provider = "bailian"          # bailian | zhipu | siliconflow | volcengine | openai | gemini | openrouter | xai
model = ""                    # empty → the catalogue's default for the provider
api_key = "${IMAGE_API_KEY}"  # empty → the chat model's key when the host is the same

[video]
provider = "bailian"          # clips speak a video-generation API this round
model = ""
api_key = "${VIDEO_API_KEY}"
```

`provider` is an id from `dragon/llm/providers.json`; `base_url` overrides it for a host
the catalogue does not list. The same settings are editable in the web app under
Connections → Making pictures / clips, and land in `<data_dir>/app-settings.json` with
the keys in the vault.

With no image/video provider configured, the studio simply says so — chat is unaffected.

## What it is for

- **An avatar for the agent** — one consistent face for the web app and channels.
- **Illustration inside a task** — "make a diagram of this" / "draw the scene for the
  story in workspace/notes" produce files in the workspace like any other tool output.
- **Short clips** — an animated avatar segment; generation takes minutes and counts as a
  billable call on your video provider's side.

## Notes

- Every generation is a tool call: it goes through the Sentinel (risk `moderate`) and is
  visible in the audit log.
- Files are saved into the workspace, so they are part of normal backups.
- Where your provider stores prompts and outputs is that provider's business — check its
  policy before generating anything private. Nothing is stored anywhere by Dragon but
  the result.
