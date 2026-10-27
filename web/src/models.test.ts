import { describe, expect, it } from "vitest";
import { currentChoice, endpointChoice, endpointGroups, endpointLabel, endpointOf, entryFor, handsValue, mediaChoices, providerLabel, slotValue } from "./models";
import type { CustomEndpoint, MediaSlotData } from "./types";

const BAILIAN = "https://dashscope.aliyuncs.com/compatible-mode/v1";

function slot(over: Partial<MediaSlotData>): MediaSlotData {
  return {
    provider: "",
    provider_id: "",
    model: "",
    base_url: "",
    key_source: "none",
    configured: false,
    from_app: false,
    effective_provider: "",
    effective_model: "",
    effective_source: "",
    ...over,
  };
}

describe("the model slots (the Models contract)", () => {
  it("finds the catalogue entry a slot stands on, by id or by host", () => {
    expect(entryFor("bailian", "")?.id).toBe("bailian");
    expect(entryFor("openai", BAILIAN)?.id).toBe("bailian");
    expect(entryFor("openai", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")?.id).toBe("bailian");
    expect(entryFor("openai", "https://api.openai.com/v1")?.id).toBe("openai");
    expect(entryFor("openai", "https://gateway.example.com/v1")).toBeNull();
    expect(entryFor("openai", "")).toBeNull();
  });

  it("writes a row's value as provider · model", () => {
    expect(slotValue(slot({ effective_provider: "bailian", effective_model: "qwen-image-3.0" }), "en")).toBe("Alibaba Cloud Bailian · qwen-image-3.0");
    expect(slotValue(slot({ effective_provider: "zhipu", effective_model: "glm-image" }), "zh-CN")).toBe("智谱 GLM · glm-image");
    expect(slotValue(slot({ effective_provider: "zhipu", effective_model: "glm-image" }), "en")).toBe("Zhipu GLM · glm-image");
    expect(slotValue(slot({ effective_provider: "custom", effective_model: "flux-2", base_url: "https://images.example.com/v1" }), "en")).toBe(
      "images.example.com · flux-2",
    );
    expect(slotValue(slot({}), "en")).toBe("");
    expect(providerLabel("nope", "en")).toBe("nope");
  });

  it("offers only own-key providers with the capability", () => {
    const chat = { provider: "openai", base_url: BAILIAN };
    const video = mediaChoices("video", { chat, region: "cn", locale: "en" });
    expect(video.map((c) => [c.value, c.group, c.needsKey])).toEqual([
      ["bailian", "chat", false],
      ["custom", "add", false],
    ]);
    // a chat provider without the capability: the catalogue's own only
    const deepseek = { provider: "openai", base_url: "https://api.deepseek.com" };
    const image = mediaChoices("image", { chat: deepseek, region: "global", locale: "en" });
    expect(image.find((c) => c.group === "chat")).toBeUndefined();
    expect(image.filter((c) => c.group === "add" && c.entry).every((c) => c.entry?.capabilities.includes("image"))).toBe(true);
    expect(image.slice(0, 2).map((c) => c.value)).toEqual(["openrouter", "openai"]);
    expect(image.every((c) => c.value !== "deepseek")).toBe(true);
    // a chat model on a host of one's own is not an own provider; nothing in the chat group
    const custom = mediaChoices("video", { chat: { provider: "openai", base_url: "https://relay.example/v1" }, region: "global", locale: "en" });
    expect(custom.map((c) => c.value)).toEqual(["custom"]);
  });

  it("writes the hands row's value from the effective fields, so Automatic shows what it resolves to", () => {
    const gui = { provider: "openai", provider_id: "", base_url: "" };
    const bailian = { provider: "openai", base_url: BAILIAN };
    // the chat provider's own hands model
    expect(handsValue({ ...gui, effective_model: "qwen3.8-27b", effective_source: "chat" }, bailian, "en")).toBe("Alibaba Cloud Bailian · qwen3.8-27b");
    expect(handsValue({ ...gui, effective_model: "qwen3.8-27b", effective_source: "chat" }, bailian, "zh-CN")).toBe("阿里云百炼 · qwen3.8-27b");
    // a model picked by hand: on the chat endpoint, on a catalogue provider of its own, on an unlisted host
    const deepseek = { provider: "openai", base_url: "https://api.deepseek.com" };
    expect(handsValue({ ...gui, effective_model: "glm-4.6v", effective_source: "gui" }, { provider: "zhipu", base_url: "" }, "en")).toBe("Zhipu GLM · glm-4.6v");
    expect(handsValue({ provider: "bailian", provider_id: "bailian", base_url: "", effective_model: "qwen3.8-27b", effective_source: "gui" }, deepseek, "en")).toBe(
      "Alibaba Cloud Bailian · qwen3.8-27b",
    );
    expect(handsValue({ provider: "openai", provider_id: "", base_url: "https://gateway.example.com/v1", effective_model: "ui-tars", effective_source: "gui" }, deepseek, "en")).toBe(
      "gateway.example.com · ui-tars",
    );
    expect(handsValue({ ...gui, effective_model: "", effective_source: "chat" }, deepseek, "en")).toBe("");
    expect(handsValue({ ...gui, effective_model: "gpt-5.6", effective_source: "chat" }, { provider: "chatgpt", base_url: "" }, "en")).toBe("ChatGPT · gpt-5.6");
  });

  it("reads the picker's value back from what the runtime reports", () => {
    expect(currentChoice(slot({}))).toBe("");
    expect(currentChoice(slot({ configured: true, provider: "zhipu", provider_id: "zhipu" }))).toBe("zhipu");
    expect(currentChoice(slot({ configured: true, provider: "openai", base_url: "https://images.example.com/v1" }))).toBe("custom");
  });
});

describe("several endpoints of one's own (#294)", () => {
  const gateway: CustomEndpoint = {
    id: "ep-1a2b3c4d",
    label: "my gateway",
    base_url: "https://gateway.example/v1",
    key_source: "vault",
    models: ["ui-tars", "deepseek-chat", "qwen3-vl"],
    slots: ["chat"],
  };
  const local: CustomEndpoint = { id: "ep-9f9f9f9f", label: "", base_url: "http://127.0.0.1:8000/v1", key_source: "none", models: ["llava"], slots: [] };
  const endpoints = [gateway, local];

  it("names a picker value after the endpoint and reads it back", () => {
    expect(endpointChoice("ep-1a2b3c4d")).toBe("endpoint:ep-1a2b3c4d");
    expect(endpointOf("endpoint:ep-1a2b3c4d")).toBe("ep-1a2b3c4d");
    expect(endpointOf("endpoint:")).toBeNull();
    expect(endpointOf("bailian")).toBeNull();
  });

  it("reads an endpoint by its name, else by its host with the port", () => {
    expect(endpointLabel(gateway)).toBe("my gateway");
    expect(endpointLabel(local)).toBe("127.0.0.1:8000");
    expect(endpointLabel({ label: "  ", base_url: "not a url" })).toBe("not a url");
  });

  it("offers the endpoints to the media pickers between the chat provider and the catalogue", () => {
    const chat = { provider: "openai", base_url: BAILIAN };
    const image = mediaChoices("image", { chat, region: "cn", locale: "en", endpoints });
    expect(image.slice(0, 3).map((c) => [c.value, c.label, c.group, c.needsKey])).toEqual([
      ["bailian", "Alibaba Cloud Bailian", "chat", false],
      ["endpoint:ep-1a2b3c4d", "my gateway", "endpoints", false],
      ["endpoint:ep-9f9f9f9f", "127.0.0.1:8000", "endpoints", false],
    ]);
    expect(image[image.length - 1].value).toBe("custom");
    // a slot standing on one reads back as that endpoint, whatever its host
    expect(currentChoice(slot({ configured: true, provider: "openai", base_url: gateway.base_url, endpoint: gateway.id }))).toBe("endpoint:ep-1a2b3c4d");
    expect(slotValue(slot({ effective_provider: "custom", effective_model: "flux-2", base_url: gateway.base_url, endpoint: gateway.id }), "en", undefined, endpoints)).toBe(
      "my gateway · flux-2",
    );
    // without the list (an older runtime) the host stands, as before
    expect(slotValue(slot({ effective_provider: "custom", effective_model: "flux-2", base_url: gateway.base_url, endpoint: gateway.id }), "en")).toBe("gateway.example · flux-2");
  });

  it("gives the hands picker one group per other endpoint, less the models known not to see", () => {
    const groups = endpointGroups(endpoints, "ep-9f9f9f9f");
    expect(groups.map((g) => [g.key, g.label, g.rows.map((r) => r.id)])).toEqual([["endpoint:ep-1a2b3c4d", "my gateway", ["ui-tars", "qwen3-vl"]]]);
    expect(endpointGroups([{ ...gateway, models: ["deepseek-chat"] }])).toEqual([]);
  });

  it("writes the hands row's value with the endpoint's name", () => {
    const deepseek = { provider: "openai", base_url: "https://api.deepseek.com" };
    const onGateway = { provider: "openai", provider_id: "", base_url: gateway.base_url, endpoint: gateway.id, effective_model: "ui-tars", effective_source: "gui" as const };
    expect(handsValue(onGateway, deepseek, "en", undefined, endpoints)).toBe("my gateway · ui-tars");
    expect(handsValue(onGateway, deepseek, "en")).toBe("gateway.example · ui-tars");
    // riding on a chat model that answers through an endpoint
    const chatOnLocal = { provider: "openai", base_url: local.base_url, endpoint: local.id };
    expect(handsValue({ provider: "openai", provider_id: "", base_url: "", effective_model: "llava", effective_source: "chat" }, chatOnLocal, "en", undefined, endpoints)).toBe(
      "127.0.0.1:8000 · llava",
    );
  });
});
