import { FileText } from "lucide-react";
import { DocumentItem } from "./DocumentItem";
import { ErrorState, Skeleton } from "@/components/common/LoadingState";
import { Button } from "@/components/common/Button";
import type { DocumentInfo } from "@/types";

interface DocumentListProps {
  documents: DocumentInfo[];
  selectedId: string | null;
  loading: boolean;
  error: string | null;
  deletingId: string | null;
  query: string;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRetry: () => void;
}

export function DocumentList({
  documents,
  selectedId,
  loading,
  error,
  deletingId,
  query,
  onSelect,
  onDelete,
  onRetry,
}: DocumentListProps) {
  if (loading && documents.length === 0) {
    return (
      <div className="space-y-2 px-3 py-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-[68px] w-full" />
        ))}
      </div>
    );
  }

  if (error && documents.length === 0) {
    return (
      <div className="px-3 py-2">
        <ErrorState
          title="Couldn't load documents"
          message={error}
          action={
            <Button size="sm" variant="outline" onClick={onRetry}>
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  const filtered = query
    ? documents.filter((d) => d.filename.toLowerCase().includes(query.toLowerCase()))
    : documents;

  if (documents.length === 0) {
    return (
      <div className="px-4 py-10 text-center">
        <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-surface-hover text-faint">
          <FileText className="h-5 w-5" aria-hidden />
        </span>
        <p className="mt-3 text-[13px] font-medium text-content">No documents yet</p>
        <p className="mt-1 text-xs text-muted">Upload a PDF to start asking questions.</p>
      </div>
    );
  }

  if (filtered.length === 0) {
    return <p className="px-4 py-8 text-center text-xs text-muted">No documents match “{query}”.</p>;
  }

  return (
    <ul className="space-y-1 px-2 py-2">
      {filtered.map((doc) => (
        <DocumentItem
          key={doc.document_id}
          doc={doc}
          selected={doc.document_id === selectedId}
          deleting={deletingId === doc.document_id}
          onSelect={() => onSelect(doc.document_id)}
          onDelete={() => onDelete(doc.document_id)}
        />
      ))}
    </ul>
  );
}
