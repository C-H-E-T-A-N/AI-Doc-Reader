import { api } from "./client";
import type { ChatResponse } from "@/types";

/**
 * Ask a question. When `documentId` is provided the backend restricts
 * retrieval to that single document; otherwise it searches everything.
 */
export function askQuestion(
  question: string,
  documentId?: string,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return api.postJson<ChatResponse>(
    "/chat",
    { question, ...(documentId ? { document_id: documentId } : {}) },
    { signal, timeoutMs: 90_000 },
  );
}
