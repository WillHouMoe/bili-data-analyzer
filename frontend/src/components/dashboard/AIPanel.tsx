import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowLeftIcon } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { AIPreset, AIConversation, AIMessageItem, ToolCallInfo } from "@/types";
import AIPresetSelector from "@/components/ai/AIPresetSelector";
import AIConversationView from "@/components/ai/AIConversationView";
import AIMessageInput from "@/components/ai/AIMessageInput";

interface AIPanelProps {
  uid?: number;
  queryId?: number;
  bvid?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type PanelState = "presets" | "streaming" | "chat" | "error";

const QUERY_PRESETS: AIPreset[] = [
  { id: "overall_analysis", labelKey: "ai.presets.overallAnalysis", descriptionKey: "ai.presets.overallAnalysisDesc", icon: "chart" },
  { id: "topic_inspiration", labelKey: "ai.presets.topicInspiration", descriptionKey: "ai.presets.topicInspirationDesc", icon: "lightbulb" },
  { id: "free_chat", labelKey: "ai.presets.freeChat", descriptionKey: "ai.presets.freeChatDesc", icon: "message" },
];

const VIDEO_PRESETS: AIPreset[] = [
  { id: "video_analysis", labelKey: "ai.presets.videoAnalysis", descriptionKey: "ai.presets.videoAnalysisDesc", icon: "video" },
];

export default function AIPanel({
  uid,
  queryId,
  bvid,
  open,
  onOpenChange,
}: AIPanelProps) {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<PanelState>("presets");
  const [conversations, setConversations] = useState<AIConversation[]>([]);
  const [currentConvId, setCurrentConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AIMessageItem[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [, setActiveTools] = useState<ToolCallInfo[]>([]);
  const [usedTools, setUsedTools] = useState<ToolCallInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const presets = bvid ? [...VIDEO_PRESETS, ...QUERY_PRESETS] : QUERY_PRESETS;

  const loadConversations = useCallback(async () => {
    try {
      const convs = bvid
        ? await api.getVideoAIConversations(bvid)
        : uid
          ? await api.getCreatorAIConversations(uid)
          : queryId
          ? await api.getAIConversations(queryId)
          : [];
      setConversations(convs);
    } catch {
      // The list keeps its last good state.
    }
  }, [uid, queryId, bvid]);

  useEffect(() => {
    if (!open) return;
    // The list is loaded on open; its setState runs inside the async callback.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadConversations();
    // Closing aborts any stream in flight; panel state survives the animation.
    return () => abortRef.current?.abort();
  }, [open, loadConversations]);

  function goBack() {
    abortRef.current?.abort();
    setState("presets");
    setCurrentConvId(null);
    setMessages([]);
    setStreamingContent("");
    setActiveTools([]);
    setUsedTools([]);
    setError(null);
    loadConversations();
  }

  // SSE stream reader
  async function readSSEStream(url: string, body: object) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStreamingContent("");
    setActiveTools([]);
    setUsedTools([]);
    setError(null);
    setState("streaming");

    let convId: number | null = null;

    try {
      const resp = await fetch(url, {
        method: "POST",
        signal: controller.signal,
        headers: {
          "Accept-Language": i18n.language,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        const msg = await resp.text().catch(() => `HTTP ${resp.status}`);
        setError(msg || `HTTP ${resp.status}`);
        setState("error");
        return;
      }

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          try {
            const event = JSON.parse(raw);

            if (event.type === "conversation_created") {
              convId = event.conversation_id;
              setCurrentConvId(event.conversation_id);
            } else if (event.type === "content") {
              accumulated += event.content;
              setStreamingContent(accumulated);
              setActiveTools([]);
            } else if (event.type === "tool_start") {
              const info: ToolCallInfo = { name: event.name, arguments: event.arguments || {} };
              setActiveTools((prev) => [...prev, info]);
              setUsedTools((prev) => [...prev, info]);
            } else if (event.type === "tool_end") {
              // Attach result to the matching tool entry
              setUsedTools((prev) => {
                const idx = prev.findLastIndex((t) => t.name === event.name && !t.result);
                if (idx >= 0) {
                  const updated = [...prev];
                  updated[idx] = { ...updated[idx], result: event.result };
                  return updated;
                }
                return prev;
              });
            } else if (event.type === "done") {
              // handled after loop
            } else if (event.type === "error") {
              setError(event.error || t("common.error"));
              setState("error");
              return;
            }
          } catch {
            // ignore non-JSON
          }
        }
      }

      // Stream finished — load conversation from DB and transition to chat
      const cid = convId ?? currentConvId;
      if (cid) {
        try {
          const detail = bvid
            ? await api.getVideoAIConversation(bvid, cid)
            : uid
              ? await api.getCreatorAIConversation(uid, cid)
              : queryId ? await api.getAIConversation(queryId, cid) : null;
          if (detail) {
            setMessages(detail.messages);
            setStreamingContent("");
            setActiveTools([]);
            setUsedTools([]);
            setState("chat");
            return;
          }
        } catch {
          // fall through
        }
      }
      // Fallback: if no detail loaded, still transition to chat
      setStreamingContent("");
      setActiveTools([]);
      setUsedTools([]);
      setState("chat");
    } catch (err: unknown) {
      if ((err as Error)?.name !== "AbortError") {
        setError((err as Error)?.message || t("common.error"));
        setState("error");
      }
    }
  }

  // Create new conversation
  async function handlePresetSelect(presetId: string) {
    if (presetId === "free_chat") {
      // Go to chat state with input — user types first message
      setState("chat");
      setMessages([]);
      setCurrentConvId(null);
      return;
    }

    const url = bvid
      ? api.createVideoAIConversationUrl(bvid)
      : uid
        ? api.createCreatorAIConversationUrl(uid)
        : queryId ? api.createAIConversationUrl(queryId) : null;
    if (!url) return;

    await readSSEStream(url, { preset: presetId });
  }

  // Resume existing conversation
  async function handleResume(convId: number) {
    setCurrentConvId(convId);
    setState("chat");
    setStreamingContent("");
    setActiveTools([]);
    setUsedTools([]);

    try {
      const detail = bvid
        ? await api.getVideoAIConversation(bvid, convId)
        : uid
          ? await api.getCreatorAIConversation(uid, convId)
          : queryId ? await api.getAIConversation(queryId, convId) : null;
      if (detail) {
        setMessages(detail.messages);
      }
    } catch {
      setError(t("common.error"));
      setState("error");
    }
  }

  // Delete conversation
  async function handleDelete(convId: number) {
    // Optimistic update — remove from UI immediately
    setConversations((prev) => prev.filter((c) => c.id !== convId));
    if (currentConvId === convId) {
      goBack();
    }
    try {
      if (bvid) {
        await api.deleteVideoAIConversation(bvid, convId);
      } else if (uid) {
        await api.deleteCreatorAIConversation(uid, convId);
      } else if (queryId) {
        await api.deleteAIConversation(queryId, convId);
      }
    } catch {
      // Re-fetch on failure to restore accurate state
      loadConversations();
    }
  }

  // Send follow-up message (or first message for free_chat)
  async function handleSendMessage(content: string) {
    // Add user message to display immediately
    const tempMsg: AIMessageItem = {
      id: Date.now(),
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempMsg]);

    if (!currentConvId) {
      // First message in free_chat — create conversation with content
      const url = bvid
        ? api.createVideoAIConversationUrl(bvid)
        : uid
          ? api.createCreatorAIConversationUrl(uid)
          : queryId ? api.createAIConversationUrl(queryId) : null;
      if (!url) return;

      await readSSEStream(url, { preset: "free_chat", content });
      return;
    }

    const url = bvid
      ? api.sendVideoAIMessageUrl(bvid, currentConvId)
      : uid
        ? api.sendCreatorAIMessageUrl(uid, currentConvId)
        : queryId ? api.sendAIMessageUrl(queryId, currentConvId) : null;
    if (!url) return;

    await readSSEStream(url, { content });
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-full flex-col p-0 sm:w-[min(38rem,92vw)] sm:max-w-[min(38rem,92vw)]"
      >
        <SheetHeader className="pr-10">
          <div className="flex items-center gap-2">
            {state !== "presets" && (
              <Button variant="ghost" size="icon-xs" onClick={goBack} aria-label={t("ai.backToPresets")}>
                <ArrowLeftIcon />
              </Button>
            )}
            <SheetTitle>{t("ai.title")}</SheetTitle>
          </div>
          <SheetDescription>
            {bvid
              ? bvid
              : uid
                ? `${t("colophon.creator")} ${uid}`
                : queryId ? `${t("colophon.query")} #${queryId}` : ""}
          </SheetDescription>
        </SheetHeader>

        {/* Body */}
        <div ref={scrollContainerRef} className="min-h-0 flex-1 overflow-y-auto">
          {state === "presets" && (
            <AIPresetSelector
              presets={presets}
              conversations={conversations}
              onSelect={handlePresetSelect}
              onResume={handleResume}
              onDelete={handleDelete}
            />
          )}

          {(state === "streaming" || state === "chat") && (
            <AIConversationView
              messages={messages}
              streamingContent={streamingContent}
              usedTools={usedTools}
              isStreaming={state === "streaming"}
              scrollContainerRef={scrollContainerRef}
            />
          )}

          {state === "error" && (
            <div className="flex flex-col items-start gap-3 px-4 py-6">
              <p className="text-note leading-relaxed text-mark">{error}</p>
              <Button variant="outline" size="sm" onClick={goBack}>
                {t("ai.backToPresets")}
              </Button>
            </div>
          )}
        </div>

        {/* Input — only in chat state */}
        {state === "chat" && (
          <AIMessageInput
            onSend={handleSendMessage}
            disabled={state !== "chat"}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}
