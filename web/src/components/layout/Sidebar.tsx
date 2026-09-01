import { useState } from "react";
import { Info, Plus, RefreshCw, Search } from "lucide-react";
import { DocumentList } from "@/components/documents/DocumentList";
import { StatusDot } from "@/components/common/StatusDot";
import type { ConnectionState } from "@/api/health";
import type { DocumentInfo } from "@/types";

interface SidebarProps {
  documents: DocumentInfo[];
  selectedId: string | null;
  loading: boolean;
  error: string | null;
  deletingId: string | null;
  connection: ConnectionState;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onUploadClick: () => void;
  onRefresh: () => void;
  onOpenDetails: () => void;
  hasSelection: boolean;
}

export function Sidebar({
  documents,
  selectedId,
  loading,
  error,
  deletingId,
  connection,
  onSelect,
  onDelete,
  onUploadClick,
  onRefresh,
  onOpenDetails,
  hasSelection,
}: SidebarProps) {
  const [query, setQuery] = useState("");

  return (
    <div className="flex h-full flex-col bg-surface">
      <div className="shrink-0 space-y-3 px-3 pb-2 pt-3">
        <button onClick={onUploadClick} className="btn btn-primary btn-md w-full">
          <Plus className="h-4 w-4" aria-hidden />
          Upload document
        </button>

        {documents.length > 2 && (
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint"
              aria-hidden
            />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter documents"
              aria-label="Filter documents"
              className="field h-8 pl-8 text-[13px]"
            />
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center justify-between px-4 pb-1 pt-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-faint">
          Your documents
        </span>
        <div className="flex items-center gap-0.5">
          {hasSelection && (
            <button
              onClick={onOpenDetails}
              className="btn btn-ghost h-6 w-6 p-0 xl:hidden"
              aria-label="Document details"
              title="Document details"
            >
              <Info className="h-3.5 w-3.5" aria-hidden />
            </button>
          )}
          <button
            onClick={onRefresh}
            className="btn btn-ghost h-6 w-6 p-0"
            aria-label="Refresh document list"
            title="Refresh"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden />
          </button>
        </div>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto" aria-label="Documents">
        <DocumentList
          documents={documents}
          selectedId={selectedId}
          loading={loading}
          error={error}
          deletingId={deletingId}
          query={query}
          onSelect={onSelect}
          onDelete={onDelete}
          onRetry={onRefresh}
        />
      </nav>

      <div className="shrink-0 border-t border-border px-4 py-3">
        <button
          onClick={onRefresh}
          className="flex items-center gap-2"
          title="Re-check connection"
          aria-label="Connection status — click to re-check"
        >
          <StatusDot state={connection} />
        </button>
      </div>
    </div>
  );
}
