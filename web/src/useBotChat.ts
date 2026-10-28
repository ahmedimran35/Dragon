import { useCallback } from "react";
import { api } from "./api";
import { isChief } from "./bots";
import { useT } from "./i18n";
import { useStore } from "./store";
import type { Bot, ThreadMeta } from "./types";

/**
 * Opening a bot's chat. A staff bot has exactly one chat of its own: `POST /api/threads`
 * with its id returns that chat when it exists and creates it on the first click (older
 * runtimes just create one). The chief keeps the many-chat system: a tap on it makes a new
 * chat. Either way the console lands on the chat that comes back.
 */
export function useBotChat(): (bot: Bot) => Promise<ThreadMeta | null> {
  const { dispatch, openThread, toast } = useStore();
  const t = useT();
  return useCallback(
    async (bot: Bot) => {
      try {
        const thread = await api.createThread(isChief(bot) ? t("New chat") : bot.name || t("New chat"), bot.id);
        dispatch({ type: "ws", msg: { kind: "thread", thread } });
        openThread(thread.id);
        return thread;
      } catch (e) {
        toast((e as Error).message);
        return null;
      }
    },
    [dispatch, openThread, toast, t],
  );
}
