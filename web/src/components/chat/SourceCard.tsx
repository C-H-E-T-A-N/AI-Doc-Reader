import { useState } from "react";
import { ChevronDown, FileText } from "lucide-react";
import { fileUrl } from "@/api/client";
import { formatScore } from "@/lib/format";
import type { Source } from "@/types";

interface SourceCardProps {
  source: Source;
  index: number;
  documentId: string | null;
}

export function SourceCard({ source, index, documentId }: SourceCardProps) {
  const [open, setOpen] = useState(false);
  const scoreLabel = formatScore(source.score);
  const hasText = Boolean(source.text && source.text.trim());
  const href =
    documentId != null
      ? `${fileUrl(documentId)}#page=${source.page > 0 ? source.page : 1}`
      : null;

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="flex items-center gap-2 px-3 py-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent/10 text-[11px] font-semibold text-accent">
          {index + 1}
        </span>
        <FileText className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-[12px] font-medium text-content" title={source.filename}>
          {source.filename}
        </span>
        {source.page > 0 && (
          <span className="shrink-0 text-[11px] text-muted">Page {source.page}</span>
        )}
        {scoreLabel && (
          <span className="shrink-0 rounded bg-surface-hover px-1.5 py-0.5 font-mono text-[10px] text-muted">
            {scoreLabel}
          </span>
        )}
        {hasText && (
          <button
            onClick={() => setOpen((v) => !v)}
            className="shrink-0 rounded p-0.5 text-faint hover:text-content"
            aria-expanded={open}
            aria-label={open ? "Hide passage" : "Show passage"}
          >
            <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
          </button>
        )}
      </div>

      {open && hasText && (
        <div className="border-t border-border bg-canvas px-3 py-2.5">
          <p className="text-[12.5px] leading-relaxed text-muted">“{source.text?.trim()}”</p>
          {href && (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block text-[11px] font-medium text-accent hover:underline"
            >
              Open page {source.page > 0 ? source.page : 1} in the PDF →
            </a>
          )}
        </div>
      )}
    </div>
  );
}
