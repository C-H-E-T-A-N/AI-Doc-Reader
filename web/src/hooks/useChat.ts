import { useCallback, useEffect, useRef, useState } from "react";
import { askQuestion } from "@/api/chat";
import { ApiError } from "@/api/client";
import type { ChatMessage, ThinkingStage } from "@/types";

const NOT_FOUND_PATTERNS = [
  /do(es)? not contain/i,
  /couldn['’]?t find/i,
  /could not find/i,
  /no (relevant )?information/i,
  /not (mentioned|found|available|provided) in the (document|context|provided)/i,
  /unable to (answer|find)/i,
];

function looksLikeNotFound(answer: string, hasSources: boolean): boolean {
  if (!hasSources) return true;
  return NOT_FOUND_PATTERNS.some((re) => re.test(answer));
}

const STAGE_SEQUENCE: { stage: ThinkingStage; after: number }[] = [
  { stage: "searching", after: 0 },
  { stage: "reading", after: 900 },
  { stage: "generating", after: 2200 },
];

let idSeq = 0;
const newId = () => `m${Date.now().toString(36)}-${idSeq++}`;

/**
 * Owns the conversation for a single selected document. Switching
 * documents resets the thread (default mode = one document at a time).
 */
export function useChat(documentId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [stage, setStage] = useState<ThinkingStage>("searching");
  const abortRef = useRef<AbortController | null>(null);
  const stageTimers = useRef<number[]>([]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    stageTimers.current.forEach(window.clearTimeout);
    stageTimers.current = [];
    setMessages([]);
    setPending(false);
  }, []);

  // New document -> fresh conversation.
  useEffect(() => {
    reset();
  }, [documentId, reset]);

  useEffect(() => () => reset(), [reset]);

  const send = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      if (!text || pending || !documentId) return;

      const userMsg: ChatMessage = { id: newId(), role: "user", content: text };
      setMessages((prev) => [...prev, userMsg]);
      setPending(true);
      setStage("searching");

      stageTimers.current = STAGE_SEQUENCE.map(({ stage: s, after }) =>
        window.setTimeout(() => setStage(s), after),
      );

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await askQuestion(text, documentId, controller.signal);
        const notFound = looksLikeNotFound(res.answer, res.sources.length > 0);
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: res.answer,
            sources: notFound ? [] : res.sources,
            notFound,
          },
        ]);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: err instanceof ApiError ? err.userMessage : "Something went wrong. Please try again.",
            errored: true,
          },
        ]);
      } finally {
        stageTimers.current.forEach(window.clearTimeout);
        stageTimers.current = [];
        setPending(false);
        abortRef.current = null;
      }
    },
    [documentId, pending],
  );

  const retryLast = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    // Drop everything from the last user message onward, then resend.
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === lastUser.id);
      return idx === -1 ? prev : prev.slice(0, idx);
    });
    void send(lastUser.content);
  }, [messages, send]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    stageTimers.current.forEach(window.clearTimeout);
    stageTimers.current = [];
    setPending(false);
  }, []);

  return { messages, pending, stage, send, reset, retryLast, stop };
}
