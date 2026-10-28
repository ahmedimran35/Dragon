import { LayoutGrid, ListChecks, Loader2, MessageCircle, Newspaper, SquareCheckBig, WifiOff } from "lucide-react";
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { setToken } from "./api";
import { BrandMark } from "./components/BrandMark";
import { BrowserPanel } from "./components/BrowserPanel";
import { ChatsDrawer } from "./components/ChatsDrawer";
import { Sidebar } from "./components/Sidebar";
import { ChatScreen } from "./screens/ChatScreen";
import { FeedScreen } from "./screens/FeedScreen";
import { useStore, type Tab } from "./store";
import { useT } from "./i18n";
import { cx } from "./util";

// The chat and the feed are what opens first; every other screen arrives as its own chunk
// the first time it is shown, so the first paint does not carry the provider form or the
// coding console.
const AvatarStudioScreen = lazy(() => import("./screens/AvatarStudioScreen").then((m) => ({ default: m.AvatarStudioScreen })));
const BotsScreen = lazy(() => import("./screens/BotsScreen").then((m) => ({ default: m.BotsScreen })));
const ChannelsScreen = lazy(() => import("./screens/ChannelsScreen").then((m) => ({ default: m.ChannelsScreen })));
const CodingScreen = lazy(() => import("./screens/CodingScreen").then((m) => ({ default: m.CodingScreen })));
const ConnectionsScreen = lazy(() => import("./screens/ConnectionsScreen").then((m) => ({ default: m.ConnectionsScreen })));
const GoalsScreen = lazy(() => import("./screens/GoalsScreen").then((m) => ({ default: m.GoalsScreen })));
const TasksScreen = lazy(() => import("./screens/TasksScreen").then((m) => ({ default: m.TasksScreen })));
const LibraryScreen = lazy(() => import("./screens/LibraryScreen").then((m) => ({ default: m.LibraryScreen })));
const MemoryScreen = lazy(() => import("./screens/MemoryScreen").then((m) => ({ default: m.MemoryScreen })));
const Onboarding = lazy(() => import("./screens/Onboarding").then((m) => ({ default: m.Onboarding })));
const SettingsScreen = lazy(() => import("./screens/SettingsScreen").then((m) => ({ default: m.SettingsScreen })));
const SkillsScreen = lazy(() => import("./screens/SkillsScreen").then((m) => ({ default: m.SkillsScreen })));

function Loading() {
  return (
    <div className="flex h-full min-h-[40vh] items-center justify-center text-muted">
      <Loader2 className="animate-spin" size={20} />
    </div>
  );
}

/** The five glyphs: outlined at rest, filled with the button's own ink when selected. The fill is the state. */
const glyph = (active: boolean) => ({ size: 26, strokeWidth: active ? 2 : 1.7, fill: active ? "currentColor" : "none", fillOpacity: active ? 0.18 : 0 });
const TABS: Array<{ id: Tab; label: string; icon: (active: boolean) => ReactNode }> = [
  { id: "chat", label: "Chat", icon: (a) => <MessageCircle {...glyph(a)} /> },
  { id: "feed", label: "Feed", icon: (a) => <Newspaper {...glyph(a)} /> },
  { id: "tasks", label: "Tasks", icon: (a) => <ListChecks {...glyph(a)} /> },
  { id: "goals", label: "Goals", icon: (a) => <SquareCheckBig {...glyph(a)} /> },
  { id: "library", label: "Library", icon: (a) => <LayoutGrid {...glyph(a)} /> },
];

export default function App() {
  const { state, setTab } = useStore();
  const t = useT();

  // The document title follows the agent's name — no second "Dragon" when the name
  // already carries it ("Ember Dragon" stays "Ember Dragon", not "Ember Dragon · Dragon").
  useEffect(() => {
    const name = state.profile?.name?.trim();
    document.title = !name || name.toLowerCase().includes("dragon")
      ? name || "Dragon"
      : `${name} · Dragon`;
  }, [state.profile?.name]);

  // `#connections` etc. opens a section straight away (`#ideas` is Tasks' old name).
  useEffect(() => {
    const jump = () => {
      const raw = window.location.hash.slice(1);
      const wanted = (raw === "ideas" ? "tasks" : raw) as Tab;
      if (wanted && TABS.some((x) => x.id === wanted)) setTab(wanted);
      else if (wanted === "memory" || wanted === "connections" || wanted === "channels" || wanted === "skills" || wanted === "coding" || wanted === "avatar" || wanted === "bots") setTab(wanted);
    };
    jump();
    window.addEventListener("hashchange", jump);
    return () => window.removeEventListener("hashchange", jump);
  }, [setTab]);

  if (state.authError) return <TokenGate />;
  // Nothing has arrived from the runtime yet: say so, instead of an empty chat.
  if (!state.loaded) return <Connecting error={state.error} />;
  // First run: the server has not seen setup finish and nothing has been said yet.
  if (!state.lite && state.settings && !state.settings.onboarded && !state.onboardingDismissed && !state.threads.some((t) => t.events > 0)) {
    return (
      <Suspense fallback={<Loading />}>
        <Onboarding />
      </Suspense>
    );
  }

  const pendingApprovals = state.pendingApprovals.length;
  const proposals = state.goals.filter((g) => g.proposal && g.status !== "cancelled").length;
  const feedUnseen = state.pendingApprovals.filter((a) => a.ts > state.feedSeenAt).length;

  // One column at narrow widths; on a wide screen a sidebar takes over from the tab bar and
  // the chats sheet — same screens either side.
  return (
    <div className={cx("mx-auto flex h-[100dvh] max-w-[760px] flex-col bg-bg sm:border-x sm:border-border", !state.lite && "wide:max-w-none wide:flex-row wide:border-x-0")}>
      {!state.lite && (
        <div className="hidden wide:block wide:h-full">
          <Sidebar />
        </div>
      )}
      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
        {state.gone && (
          <div className="flex items-center justify-center gap-2 bg-surface-2 text-muted text-[12.5px] py-1">
            <WifiOff size={14} /> {t(state.lite ? "This demo has ended." : "This Dragon has stopped. Reload the page once it is running again.")}
          </div>
        )}
        {!state.gone && !state.connected && state.loaded && (
          <div className="flex items-center justify-center gap-2 bg-amber-500/15 text-amber-700 dark:text-amber-300 text-[12.5px] py-1">
            <WifiOff size={14} /> {t("Reconnecting to your Dragon…")}
          </div>
        )}
        {/* `tabbar-room` keeps the screens, the chat's composer included, above the floating bar;
            a wide window has the sidebar instead and gives the room back. */}
        <main className={cx("tabbar-room mx-auto min-h-0 w-full flex-1 wide:max-w-[900px]", !state.lite && "wide:pb-0")}>
          <Suspense fallback={<Loading />}>
            {state.tab === "chat" && <ChatScreen />}
            {state.tab === "feed" && <FeedScreen />}
            {state.tab === "tasks" && <TasksScreen />}
            {state.tab === "goals" && <GoalsScreen />}
            {state.tab === "library" && <LibraryScreen />}
            {state.tab === "memory" && <MemoryScreen />}
            {state.tab === "skills" && <SkillsScreen />}
            {state.tab === "connections" && <ConnectionsScreen />}
            {state.tab === "channels" && <ChannelsScreen />}
            {state.tab === "you" && <SettingsScreen />}
            {state.tab === "coding" && <CodingScreen />}
            {state.tab === "avatar" && <AvatarStudioScreen />}
            {state.tab === "bots" && <BotsScreen />}
          </Suspense>
        </main>
        {/* Dragon's bottom bar: a floating frosted-glass pill, five glyphs, icons only. */}
        <nav className={cx("tabbar-float pointer-events-none absolute inset-x-0 z-20 flex justify-center px-3", !state.lite && "wide:hidden")}>
          <ul className="pointer-events-auto flex w-full max-w-[420px] items-center gap-0.5 rounded-full bg-surface-2/55 px-3.5 py-2.5 ring-1 ring-border/50 backdrop-blur-3xl">
            {TABS.map((tab) => {
              const active = state.tab === tab.id;
              const badge = tab.id === "chat" ? pendingApprovals : tab.id === "feed" ? feedUnseen : tab.id === "goals" ? proposals : tab.id === "tasks" ? pendingApprovals + proposals : 0;
              return (
                <li key={tab.id} className="min-w-0 flex-1">
                  <button
                    type="button"
                    onClick={() => setTab(tab.id)}
                    aria-label={t(tab.label)}
                    aria-current={active ? "page" : undefined}
                    className={cx("flex h-[46px] w-full items-center justify-center", active ? "text-accent-fg" : "text-muted hover:text-fg")}
                  >
                    <span className={cx("relative flex h-[46px] w-full max-w-[60px] items-center justify-center rounded-full transition-colors duration-300", active && "bg-accent text-accent-fg shadow-sm")}>
                      {tab.icon(active)}
                      {badge > 0 && (
                        <span className="absolute right-2.5 top-1 flex h-[17px] min-w-[17px] items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white shadow-sm">
                          {badge}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
      {/* the chats drawer from the hamburger, over a narrow column */}
      <ChatsDrawer />
      {/* the agent's browser, live, on the right of a wide window (a phone taps a frame in the chat instead) */}
      {!state.lite && state.browserOpen && <BrowserPanel />}
      <div className="pointer-events-none hidden w-0" />
      {state.toast && (
        <div className="pointer-events-none fixed inset-x-0 bottom-[calc(6rem+env(safe-area-inset-bottom))] z-[70] flex justify-center px-4">
          <div role="status" className="rise rounded-2xl bg-fg text-bg px-4 py-2 text-[13.5px] shadow-lg max-w-sm text-center">{state.toast}</div>
        </div>
      )}
    </div>
  );
}

/** The first seconds: the socket is on its way, or the runtime cannot be reached at all. */
function Connecting({ error }: { error: string | null }) {
  const t = useT();
  return (
    <div className="mx-auto flex h-[100dvh] max-w-sm flex-col items-center justify-center px-6 text-center">
      <BrandMark size={72} />
      {error ? (
        <>
          <p className="mt-6 text-[15px] font-medium">{t("Could not reach your Dragon.")}</p>
          <p className="mt-1.5 text-[13px] text-muted">{t(error)}</p>
          <button type="button" onClick={() => window.location.reload()} className="mt-5 rounded-full bg-fg px-5 py-2 text-[14px] font-medium text-bg">
            {t("Try again")}
          </button>
        </>
      ) : (
        <p className="mt-6 flex items-center gap-2 text-[14px] text-muted">
          <Loader2 className="animate-spin" size={16} /> {t("Connecting to your Dragon…")}
        </p>
      )}
    </div>
  );
}

function TokenGate() {
  const [value, setValue] = useState("");
  const t = useT();
  return (
    <div className="mx-auto flex h-[100dvh] max-w-md flex-col items-center justify-center px-6 text-center">
      <BrandMark size={88} />
      <h1 className="mt-4 text-[22px] font-bold">{t("Connect to your Dragon")}</h1>
      <p className="mt-2 text-[14px] text-muted">
        {t("This app talks to the Dragon server you run yourself. Scan the QR code printed by")}{" "}
        <code className="rounded bg-surface-2 px-1">dragon serve</code>{t(", or paste the access token below.")}
      </p>
      <form
        className="mt-5 w-full flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!value.trim()) return;
          setToken(value.trim());
          window.location.reload();
        }}
      >
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-label={t("Access token")}
          placeholder={t("Access token")}
          className="flex-1 rounded-2xl bg-surface-2 px-4 py-2.5 text-[15px] outline-none focus:ring-2 focus:ring-accent/40"
        />
        <button type="submit" className="rounded-2xl bg-accent text-accent-fg px-4 font-medium">
          {t("Connect")}
        </button>
      </form>
    </div>
  );
}