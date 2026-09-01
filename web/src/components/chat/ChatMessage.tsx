import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Info, RotateCcw } from "lucide-react";
import { SourceCard } from "./SourceCard";
import type { ChatMessage as ChatMessageType } from "@/types";

interface ChatMessageProps {
  message: ChatMessageType;
  documentId: string | null;
  onRetry?: () => void;
}

function ChatMessageBase({ message, documentId, onRetry }: ChatMessageProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-[15px] leading-relaxed text-accent-contrast">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in space-y-3">
      {message.errored ? (
        <div className="flex items-start gap-2.5 rounded-xl border border-danger/30 bg-danger-subtle/60 px-3.5 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden />
          <div className="flex-1">
            <p className="text-[13px] text-content">{message.content}</p>
            {onRetry && (
              <button
                onClick={onRetry}
                className="mt-2 inline-flex items-center gap-1.5 text-[12px] font-medium text-accent hover:underline"
              >
                <RotateCcw className="h-3.5 w-3.5" aria-hidden />
                Retry
              </button>
            )}
          </div>
        </div>
      ) : message.notFound ? (
        <div className="flex items-start gap-2.5 rounded-xl border border-border bg-surface px-3.5 py-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden />
          <p className="text-[13px] leading-relaxed text-muted">
            {message.content?.trim() ||
              "I couldn't find this information in the selected document."}
          </p>
        </div>
      ) : (
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
      )}

      {message.sources && message.sources.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-faint">
            Sources · {message.sources.length}
          </p>
          <div className="space-y-1.5">
            {message.sources.map((s, i) => (
              <SourceCard key={`${s.filename}-${s.page}-${i}`} source={s} index={i} documentId={documentId} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export const ChatMessage = memo(ChatMessageBase);
