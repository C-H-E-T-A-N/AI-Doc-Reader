import { useState } from "react";
import { FileText, Loader2, Trash2 } from "lucide-react";
import type { DocumentInfo } from "@/types";
import { formatBytes, formatRelative } from "@/lib/format";

interface DocumentItemProps {
  doc: DocumentInfo;
  selected: boolean;
  deleting: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

export function DocumentItem({ doc, selected, deleting, onSelect, onDelete }: DocumentItemProps) {
  const [confirming, setConfirming] = useState(false);

  return (
    <li>
      <div
        className={`group relative flex items-start gap-2.5 rounded-lg border px-2.5 py-2 transition-colors ${
          selected
            ? "border-accent/40 bg-accent-subtle"
            : "border-transparent hover:border-border hover:bg-surface-hover"
        }`}
      >
        <button
          type="button"
          onClick={onSelect}
          aria-current={selected ? "true" : undefined}
          className="flex min-w-0 flex-1 items-start gap-2.5 text-left focus-visible:outline-none"
        >
          <span
            className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${
              selected ? "bg-accent/15 text-accent" : "bg-surface-hover text-muted"
            }`}
          >
            <FileText className="h-3.5 w-3.5" aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span
              className={`block truncate text-[13px] font-medium ${
                selected ? "text-content" : "text-content/90"
              }`}
              title={doc.filename}
            >
              {doc.filename}
            </span>
            <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-faint">
              <span className="uppercase">{doc.file_type}</span>
              <span aria-hidden>·</span>
              <span>{doc.pages} pages</span>
              <span aria-hidden>·</span>
              <span>{formatBytes(doc.size_bytes)}</span>
            </span>
            <span className="mt-1 flex items-center gap-1.5 text-[11px]">
              <span className="inline-flex items-center gap-1 text-positive">
                <span className="h-1.5 w-1.5 rounded-full bg-positive" aria-hidden />
                {capitalize(doc.status)}
              </span>
              <span className="text-faint" aria-hidden>
                ·
              </span>
              <span className="text-faint">{formatRelative(doc.uploaded_at)}</span>
            </span>
          </span>
        </button>

        {confirming ? (
          <div className="flex shrink-0 items-center gap-1">
            <button
              onClick={() => {
                setConfirming(false);
                onDelete();
              }}
              className="rounded px-1.5 py-0.5 text-[11px] font-medium text-danger hover:bg-danger/10"
            >
              Delete
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="rounded px-1.5 py-0.5 text-[11px] text-muted hover:bg-surface-hover"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            disabled={deleting}
            className="shrink-0 rounded p-1 text-faint transition hover:bg-danger/10 hover:text-danger focus-visible:opacity-100 md:opacity-0 md:group-hover:opacity-100"
            aria-label={`Delete ${doc.filename}`}
          >
            {deleting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="h-3.5 w-3.5" aria-hidden />
            )}
          </button>
        )}
      </div>
    </li>
  );
}

function capitalize(s: string) {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}
