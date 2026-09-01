import { ExternalLink, FileText } from "lucide-react";
import { fileUrl } from "@/api/client";
import { formatBytes, formatDate } from "@/lib/format";
import type { DocumentInfo } from "@/types";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-right text-[13px] font-medium text-content">{value}</dd>
    </div>
  );
}

export function DocumentDetails({ doc }: { doc: DocumentInfo }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-4 py-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-faint">Document</span>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
            <FileText className="h-4 w-4" aria-hidden />
          </span>
          <p className="min-w-0 break-words text-sm font-semibold text-content" title={doc.filename}>
            {doc.filename}
          </p>
        </div>

        <dl className="mt-4 divide-y divide-border">
          <Row label="Type" value={doc.file_type.toUpperCase()} />
          <Row label="Size" value={formatBytes(doc.size_bytes)} />
          <Row label="Pages" value={String(doc.pages)} />
          <Row label="Characters" value={doc.characters.toLocaleString()} />
          <Row label="Chunks indexed" value={String(doc.chunks)} />
          <Row label="Uploaded" value={formatDate(doc.uploaded_at)} />
        </dl>

        <div className="mt-4 flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2">
          <span className="h-1.5 w-1.5 rounded-full bg-positive" aria-hidden />
          <span className="text-[13px] font-medium text-content">
            {doc.status[0].toUpperCase() + doc.status.slice(1)}
          </span>
          <span className="text-xs text-muted">· ready for questions</span>
        </div>

        <a
          href={fileUrl(doc.document_id)}
          target="_blank"
          rel="noreferrer"
          className="btn btn-outline btn-sm mt-3 w-full"
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden />
          Open original PDF
        </a>
      </div>
    </div>
  );
}
