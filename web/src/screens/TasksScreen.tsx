import { Check, Clock, Flag, Loader2, MessageCircle, RefreshCw, RotateCcw, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Sheet } from "../components/Sheet";
import { TabHeader } from "../components/TabHeader";
import { useT } from "../i18n";
import { useStore, type Tab } from "../store";
import type { Task, TasksData } from "../types";
import { relativeTime } from "../util";
import { CATEGORIES } from "../goals";

/**
 * The Tasks tab: what needs the user right now (an approval, a question, a goal's plan
 * change, a goal past its date), what the agent suggests from what it knows, what it is
 * working on, what is ready for a look, and what was resolved. Every suggestion becomes a
 * task with a log — started, run, tried again, resolved — so nothing is pitched and lost
 * the way an idea was.
 */
export function TasksScreen() {
  const { state, send, openThread, setTab, toast } = useStore();
  const [data, setData] = useState<TasksData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Task | null>(null);
  const [showResolved, setShowResolved] = useState(false);
  const name = state.profile?.name ?? "Dragon";
  const t = useT();

  const load = async (refresh = false) => {
    setLoading(true);
    try {
      const d = await api.tasks(refresh);
      setData(d);
      if (d.error) toast(t("Could not refresh tasks: {error}", { error: d.error }));
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // the runtime says a task's run ended (or a card arrived): the list follows
  useEffect(() => {
    if (state.tasksVersion) void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.tasksVersion]);

  // What Start sends to the main chat: the request itself, or a goal conversation's opener first.
  const promptFor = (task: Task) => {
    if (task.kind !== "goal") return task.prompt;
    const category = CATEGORIES.find((c) => c.id === task.category) ?? CATEGORIES[CATEGORIES.length - 1];
    const opener = t("I'd like to create a {category} goal. Ask me a few short questions, one at a time (what exactly I want, why and by when, how often to check in), then create it with concrete steps using the goals tool.", {
      category: t(category.label),
    });
    return `${opener} ${task.prompt}`;
  };

  const toChat = (text: string) => {
    send("main", text).catch((e: Error) => toast(e.message || t("Could not send")));
    openThread("main");
  };

  // Start: a routine becomes a daily reminder and is done; anything else goes to the chat
  // and the task waits under Working until the run ends.
  const start = async (task: Task) => {
    setSelected(null);
    if (task.kind === "routine") {
      const time = task.time && /^([01]\d|2[0-3]):[0-5]\d$/.test(task.time) ? task.time : "09:00";
      try {
        await api.createReminder({ text: task.prompt, kind: "task", repeat: `daily ${time}` });
        await api.taskAction(task.id, "resolve", { note: t("Routine set: every day at {time}", { time }) });
        toast(t("Routine set: every day at {time}. It is listed under Goals.", { time }));
      } catch (e) {
        toast((e as Error).message);
      }
      void load(false);
      return;
    }
    try {
      await api.taskAction(task.id, "start", { thread: "main" });
    } catch (e) {
      toast((e as Error).message);
      return;
    }
    toChat(promptFor(task));
    void load(false);
  };

  const act = async (task: Task, action: "hide" | "resolve" | "retry" | "reopen") => {
    setSelected(null);
    try {
      await api.taskAction(task.id, action);
      if (action === "retry") toChat(promptFor(task));
    } catch (e) {
      toast((e as Error).message);
    }
    void load(false);
  };

  // Live rows are handled where they live: the row opens that screen.
  const open = (task: Task) => {
    setSelected(null);
    const thread = task.link?.thread ?? task.thread;
    if (thread) openThread(thread);
    const tab = task.link?.tab ?? (task.thread ? "chat" : task.kind === "run" ? "coding" : "");
    if (tab) setTab(tab as Tab);
  };

  const sections: Array<{ id: string; title: string; tasks: Task[] }> = [
    { id: "needs_you", title: t("Needs you"), tasks: data?.needs_you ?? [] },
    { id: "suggested", title: t("Suggested"), tasks: data?.suggested ?? [] },
    { id: "working", title: t("Working"), tasks: data?.working ?? [] },
    { id: "review", title: t("Ready for review"), tasks: data?.review ?? [] },
    ...(showResolved ? [{ id: "resolved", title: t("Resolved"), tasks: data?.resolved ?? [] }] : []),
  ];
  const empty = !!data && sections.every((s) => s.tasks.length === 0) && data.resolved.length === 0;

  // Dragon's Tasks page: a big title, then rows of "bold title · grey detail" under section
  // headers. Tapping a row opens a sheet with what it is, the buttons that apply to it, and
  // the log of what was done to it so far.
  return (
    <div className="flex h-full flex-col">
      <TabHeader title={t("Tasks")}>
        <button
          type="button"
          onClick={() => void load(true)}
          disabled={loading}
          aria-label={t("Refresh tasks")}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-surface text-fg shadow-[0_1px_4px_rgba(0,0,0,0.14)] disabled:opacity-60 dark:border dark:border-border dark:shadow-none"
        >
          {loading ? <Loader2 size={20} className="animate-spin" /> : <RefreshCw size={19} />}
        </button>
      </TabHeader>
      <div className="flex-1 overflow-y-auto pb-6">
        {empty && (
          <div className="space-y-1.5 px-5 pt-6 text-[14px] leading-[21px] text-muted">
            <p>{t("Nothing needs you right now.")}</p>
            <p>{t("No suggestions yet. Refresh once {name} knows you better.", { name })}</p>
          </div>
        )}
        {sections.map(({ id, title, tasks }) =>
          tasks.length === 0 ? null : (
            <section key={id}>
              <h2 className="px-5 pt-[22px] pb-1 text-[20px] font-bold">{title}</h2>
              <ul>
                {tasks.map((task) => (
                  <li key={task.id}>
                    <button type="button" onClick={() => setSelected(task)} className="flex w-full items-start gap-3 px-5 py-3.5 text-left active:bg-surface-2/70">
                      <span className="min-w-0 flex-1 space-y-1">
                        <span className="block text-[16px] font-semibold leading-[22px]">{task.title}</span>
                        {task.detail && <span className="line-clamp-4 block text-[13.5px] leading-[19px] text-muted">{task.detail}</span>}
                        <span className="flex items-center gap-1.5 pt-0.5 text-[12px] text-muted">
                          <span className="rounded-full bg-surface-2 px-2 py-[3px] leading-none">{chipOf(task, t)}</span>
                          <span>{relativeTime(task.updated_at)}</span>
                        </span>
                      </span>
                    </button>
                    <div className="mx-5 border-b border-border/70" />
                  </li>
                ))}
              </ul>
            </section>
          ),
        )}
        {!showResolved && (data?.resolved.length ?? 0) > 0 && (
          <button type="button" onClick={() => setShowResolved(true)} className="px-5 pt-4 text-[13px] font-semibold text-muted">
            {t("Show {n} more", { n: data?.resolved.length ?? 0 })}
          </button>
        )}
        {data?.generated_at && (
          <div className="px-5 pt-4 text-[12.5px] text-muted">{t("Generated {when}", { when: relativeTime(data.generated_at) })}</div>
        )}
      </div>

      <Sheet open={selected !== null} onClose={() => setSelected(null)}>
        {selected && (
          <div className="px-1 pb-2">
            <h3 className="text-[18px] font-bold leading-6">{selected.title}</h3>
            {selected.detail && <p className="mt-3 text-[15px] leading-[22px]">{selected.detail}</p>}
            <div className="mt-3.5 flex items-center gap-2 text-[13px] text-muted">
              <span className="rounded-full bg-surface-2 px-2 py-[3px] leading-none">{chipOf(selected, t)}</span>
              {kindLine(selected, t)}
            </div>
            <div className="mt-[22px] space-y-2">
              {selected.status === "needs_you" && (
                <button type="button" onClick={() => open(selected)} className="flex h-[50px] w-full items-center justify-center gap-2 rounded-full bg-accent text-[16px] font-semibold text-accent-fg">
                  {t("Open")}
                </button>
              )}
              {selected.status === "suggested" && (
                <>
                  <button type="button" onClick={() => void start(selected)} className="flex h-[50px] w-full items-center justify-center gap-2 rounded-full bg-accent text-[16px] font-semibold text-accent-fg">
                    {selected.kind === "routine" ? (
                      <>
                        <Clock size={18} /> {t("Create routine")}
                      </>
                    ) : selected.kind === "goal" ? (
                      <>
                        <Flag size={18} /> {t("Start goal")}
                      </>
                    ) : (
                      <>
                        <MessageCircle size={18} /> {t("Send to chat")}
                      </>
                    )}
                  </button>
                  <button type="button" onClick={() => void act(selected, "hide")} className="flex h-[50px] w-full items-center justify-center gap-2 rounded-full bg-surface-2 text-[16px] font-semibold">
                    <X size={18} /> {t("Hide")}
                  </button>
                </>
              )}
              {selected.status === "working" && (
                <>
                  {(selected.thread || selected.link || selected.kind === "run") && (
                    <button type="button" onClick={() => open(selected)} className="flex h-[50px] w-full items-center justify-center gap-2 rounded-full bg-accent text-[16px] font-semibold text-accent-fg">
                      {t("Open")}
                    </button>
                  )}
                  <button type="button" onClick={() => void act(selected, "resolve")} className="flex h-[50px] w-full items-center justify-center gap-2 rounded-full bg-surface-2 text-[16px] font-semibold">
                    <Check size={18} /> {t("Resolve")}
                  </button>
                </>
              )}
              {selected.status === "review" && (
                <>
                  <button type="button" onClick={() => void act(selected, "resolve")} className="flex h-[50px] w-full items-center justify-center gap-2 rounded-full bg-accent text-[16px] font-semibold text-accent-fg">
                    <Check size={18} /> {t("Resolve")}
                  </button>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => void act(selected, "retry")} className="flex h-[50px] flex-1 items-center justify-center gap-2 rounded-full bg-surface-2 text-[15px] font-semibold">
                      <RotateCcw size={17} /> {t("Try again")}
                    </button>
                    {selected.thread && (
                      <button type="button" onClick={() => open(selected)} className="flex h-[50px] flex-1 items-center justify-center gap-2 rounded-full bg-surface-2 text-[15px] font-semibold">
                        {t("Open")}
                      </button>
                    )}
                  </div>
                </>
              )}
              {selected.status === "resolved" && (
                <button type="button" onClick={() => void act(selected, "reopen")} className="flex h-[50px] w-full items-center justify-center gap-2 rounded-full bg-surface-2 text-[16px] font-semibold">
                  <RotateCcw size={18} /> {t("Reopen")}
                </button>
              )}
            </div>
            {selected.attempts.length > 0 && (
              <div className="mt-6">
                <h4 className="text-[13px] font-semibold text-muted">{t("History")}</h4>
                <ul className="mt-1.5 space-y-1.5">
                  {selected.attempts.map((a, i) => (
                    <li key={`${a.at}-${i}`} className="flex items-baseline gap-2 text-[13px] leading-[19px]">
                      <span className="shrink-0 text-muted">{relativeTime(a.at)}</span>
                      <span>
                        {t(a.outcome)}
                        {a.note ? ` · ${a.note}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Sheet>
    </div>
  );
}

/** The small state label on a row: the live item's kind, or the task's status. */
function chipOf(task: Task, t: (key: string, vars?: Record<string, string | number>) => string): string {
  switch (task.kind) {
    case "approval":
      return t("Needs your approval");
    case "question":
      return t("Waiting for your answer");
    case "proposal":
      return t("Plan change waiting for your decision");
    case "overdue":
      return t("Past its due date");
    case "run":
      return t("Working");
    default:
      break;
  }
  switch (task.status) {
    case "suggested":
      return t("Suggested");
    case "working":
      return t("Working");
    case "review":
      return t("Ready for review");
    case "resolved":
      return t("Resolved");
    default:
      return t("Needs you");
  }
}

/** What starting this task does, said under its title in the sheet. */
function kindLine(task: Task, t: (key: string, vars?: Record<string, string | number>) => string): string | null {
  if (task.kind === "routine") return `${t("Creates a routine")}${task.time ? ` · ${task.time}` : ""}`;
  if (task.kind === "goal") return t("Creates a goal");
  if (task.kind === "chat") return t("Starts a conversation");
  return null;
}
