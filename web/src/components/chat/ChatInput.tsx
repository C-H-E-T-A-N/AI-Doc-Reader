import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { ArrowUp, Square } from "lucide-react";

interface ChatInputProps {
  disabled?: boolean;
  pending?: boolean;
  documentName?: string | null;
  onSend: (text: string) => void;
  onStop?: () => void;
  /** Controlled seed value (e.g. from an example card). */
  seed?: string;
  seedNonce?: number;
}

const MAX_HEIGHT = 200;
const MIN_HEIGHT = 24;

export function ChatInput({
  disabled,
  pending,
  documentName,
  onSend,
  onStop,
  seed,
  seedNonce,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (seed != null) {
      setValue(seed);
      requestAnimationFrame(() => {
        ref.current?.focus();
        resize();
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed, seedNonce]);

  const resize = () => {
    const el = ref.current;
    if (!el) return;
    // Collapse to a known baseline before measuring so a stale height
    // (e.g. mid-reflow) can't inflate scrollHeight.
    el.style.height = "0px";
    const next = Math.min(Math.max(el.scrollHeight, MIN_HEIGHT), MAX_HEIGHT);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
  };

  useEffect(resize, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled || pending) return;
    onSend(text);
    setValue("");
    requestAnimationFrame(resize);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-border bg-canvas px-3 pb-4 pt-3 sm:px-6">
      <div className="mx-auto max-w-3xl">
        {documentName && (
          <p className="mb-1.5 px-1 text-[11px] text-faint">
            Answering from <span className="font-medium text-muted">{documentName}</span>
          </p>
        )}
        <div
          className={`flex items-end gap-2 rounded-xl border bg-elevated px-2.5 py-2 transition-colors ${
            disabled ? "border-border opacity-60" : "border-border-strong focus-within:border-accent"
          }`}
        >
          <textarea
            ref={ref}
            rows={1}
            value={value}
            disabled={disabled}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={
              disabled ? "Select a document to start asking questions" : "Ask anything about this document…"
            }
            aria-label="Ask a question about the selected document"
            className="max-h-[200px] flex-1 resize-none bg-transparent px-1.5 py-1.5 text-[15px] leading-relaxed text-content placeholder:text-faint focus:outline-none"
          />
          {pending ? (
            <button
              onClick={onStop}
              className="btn btn-outline h-9 w-9 shrink-0 p-0"
              aria-label="Stop generating"
              title="Stop"
            >
              <Square className="h-3.5 w-3.5 fill-current" aria-hidden />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={disabled || !value.trim()}
              className="btn btn-primary h-9 w-9 shrink-0 p-0"
              aria-label="Send question"
              title="Send"
            >
              <ArrowUp className="h-4 w-4" aria-hidden />
            </button>
          )}
        </div>
        <p className="mt-1.5 px-1 text-center text-[11px] text-faint">
          Enter to send · Shift + Enter for a new line
        </p>
      </div>
    </div>
  );
}
