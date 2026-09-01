import { useEffect, useMemo, useRef, useState } from "react";
import { Info, Trash2 } from "lucide-react";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { EmptyState } from "./EmptyState";
import { useChat } from "@/hooks/useChat";
import type { DocumentInfo } from "@/types";

interface ChatWindowProps {
  document: DocumentInfo | null;
  onUploadClick: () => void;
  onOpenDetails: () => void;
  showDetailsButton: boolean;
}

export function ChatWindow({ document, onUploadClick, onOpenDetails, showDetailsButton }: ChatWindowProps) {
  const documentId = document?.document_id ?? null;
  const { messages, pending, stage, send, reset, retryLast, stop } = useChat(documentId);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [seed, setSeed] = useState<string | undefined>(undefined);
  const [seedNonce, setSeedNonce] = useState(0);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, pending]);

  const pickExample = (q: string) => {
    setSeed(q);
    setSeedNonce((n) => n + 1);
  };

  const headerStatus = useMemo(() => {
    if (!document) return null;
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] text-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-positive" aria-hidden />
        Ready
      </span>
    );
  }, [document]);

  return (
    <section className="flex h-full min-w-0 flex-1 flex-col bg-canvas">
      {document && (
        <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-border px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="truncate text-[13px] font-medium text-content" title={document.filename}>
              {document.filename}
            </span>
            {headerStatus}
          </div>
          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <button
                onClick={reset}
                className="btn btn-ghost btn-sm gap-1.5 text-xs"
                aria-label="Clear conversation"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden />
                <span className="hidden sm:inline">Clear</span>
              </button>
            )}
            {showDetailsButton && (
              <button
                onClick={onOpenDetails}
                className="btn btn-ghost h-8 w-8 p-0 xl:hidden"
                aria-label="Document details"
              >
                <Info className="h-4 w-4" aria-hidden />
              </button>
            )}
          </div>
        </div>
      )}

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        {messages.length === 0 && !pending ? (
          <EmptyState hasDocument={!!document} onPick={pickExample} onUpload={onUploadClick} />
        ) : (
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6">
            {messages.map((m, i) => (
              <ChatMessage
                key={m.id}
                message={m}
                documentId={documentId}
                onRetry={m.errored && i === messages.length - 1 ? retryLast : undefined}
              />
            ))}
            {pending && (
              <div className="pt-1">
                <ThinkingIndicator stage={stage} />
              </div>
            )}
          </div>
        )}
      </div>

      <ChatInput
        disabled={!document}
        pending={pending}
        documentName={document?.filename ?? null}
        onSend={send}
        onStop={stop}
        seed={seed}
        seedNonce={seedNonce}
      />
    </section>
  );
}
