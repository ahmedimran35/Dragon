import { createElement } from "react";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { LoadError } from "../components/LoadError";
import type { SkillCatalogData } from "../types";
import { SkillCatalogScreen } from "./SkillCatalogScreen";

const store = vi.hoisted(() => ({ toast: () => {} }));
vi.mock("../store", () => ({ useStore: () => store }));

const catalog: SkillCatalogData = {
  source: "https://agenticskills.io/skills",
  total: 2,
  auto_sync: false,
  last_sync: "",
  last_error: "",
  status: { running: false, done: 0, total: 0, failed: 0, errors: [] },
  items: [
    {
      slug: "first-one", name: "First One", description: "Does the first job.",
      url: "https://agenticskills.io/skills/first-one", installed: false, skill: "",
    },
    {
      slug: "second-one", name: "Second One", description: "Does the second job.",
      url: "https://agenticskills.io/skills/second-one", installed: false, skill: "",
    },
  ],
};

let screen: ReactTestRenderer;

beforeEach(() => {
  vi.spyOn(api, "skillCatalog").mockResolvedValue(structuredClone(catalog));
  vi.spyOn(api, "skillCatalogStatus").mockResolvedValue(catalog.status);
  vi.spyOn(api, "importCatalogSkill").mockResolvedValue({
    skill: {} as never, license: "", github_url: "",
  });
  vi.spyOn(api, "importAllCatalogSkills").mockResolvedValue(catalog.status);
  vi.spyOn(api, "setCatalogAuto").mockResolvedValue({ ...catalog, auto_sync: true });
});

afterEach(() => {
  if (screen) act(() => screen.unmount());
  vi.restoreAllMocks();
});

async function mount() {
  await act(async () => { screen = create(createElement(SkillCatalogScreen, { onBack: () => {} })); });
}

it("shows the public catalog and imports a skill, marking it added", async () => {
  await mount();
  expect(vi.mocked(api.skillCatalog)).toHaveBeenCalled();
  expect(JSON.stringify(screen.toJSON())).toContain("First One");
  expect(JSON.stringify(screen.toJSON())).toContain("agenticskills.io");

  const add = screen.root.findAllByType("button").filter((n) => n.children.includes("Add"));
  const first = add[0];
  expect(first).toBeDefined();
  await act(async () => { first.props.onClick(); });
  expect(vi.mocked(api.importCatalogSkill)).toHaveBeenCalledWith("first-one");
  expect(JSON.stringify(screen.toJSON())).toContain("Added");
});

it("offers a retry when the catalog cannot be read", async () => {
  vi.mocked(api.skillCatalog).mockRejectedValueOnce(new Error("directory offline"));
  await mount();
  const error = screen.root.findAllByType(LoadError).find((n) => n.props.message === "directory offline");
  expect(error).toBeDefined();
  await act(async () => { error!.findByType("button").props.onClick(); });
  expect(vi.mocked(api.skillCatalog)).toHaveBeenCalledTimes(2);
});

it("can turn on automatic sync", async () => {
  await mount();
  const toggle = screen.root.findAllByType("button").find((n) => n.props.role === "switch");
  expect(toggle).toBeDefined();
  await act(async () => { toggle!.props.onClick(); });
  expect(vi.mocked(api.setCatalogAuto)).toHaveBeenCalledWith(true);
});
