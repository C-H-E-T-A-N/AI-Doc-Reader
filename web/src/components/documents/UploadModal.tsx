import { useCallback, useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import { CheckCircle2, FileText, UploadCloud, XCircle } from "lucide-react";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/common/Button";
import { formatBytes } from "@/lib/format";
import type { UploadProgress } from "@/hooks/useDocuments";

const ACCEPT = ".pdf,application/pdf";
const MAX_MB = 25;

const STAGE_STEPS = ["Uploading file", "Extracting text", "Creating embeddings", "Indexing document"];

interface UploadModalProps {
  open: boolean;
  progress: UploadProgress | null;
  onClose: () => void;
  onUpload: (file: File) => void;
  onDone: () => void;
}

export function UploadModal({ open, progress, onClose, onUpload, onDone }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const doneHandled = useRef(false);

  const busy = progress?.stage === "uploading" || progress?.stage === "processing";
  const failed = progress?.stage === "error";
  const succeeded = progress?.stage === "done";

  useEffect(() => {
    if (!open) {
      setFile(null);
      setLocalError(null);
      setDragging(false);
      doneHandled.current = false;
    }
  }, [open]);

  useEffect(() => {
    if (succeeded && !doneHandled.current) {
      doneHandled.current = true;
      const t = window.setTimeout(onDone, 700);
      return () => window.clearTimeout(t);
    }
  }, [succeeded, onDone]);

  const validateAndSet = useCallback((f: File | undefined) => {
    setLocalError(null);
    if (!f) return;
    const isPdf = f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setLocalError("Only PDF files are supported in this version.");
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setLocalError(`That file is ${formatBytes(f.size)}. The limit is ${MAX_MB} MB.`);
      return;
    }
    setFile(f);
  }, []);

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (!busy) validateAndSet(e.dataTransfer.files?.[0]);
    },
    [busy, validateAndSet],
  );

  return (
    <Modal
      open={open}
      onClose={busy ? () => undefined : onClose}
      title="Upload a document"
      description="PDF, up to 25 MB. It will be parsed, embedded and indexed for Q&A."
      footer={
        !progress ? (
          <>
            <Button variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button size="sm" disabled={!file} onClick={() => file && onUpload(file)}>
              Upload &amp; analyze
            </Button>
          </>
        ) : null
      }
    >
      {!progress && (
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
            dragging ? "border-accent bg-accent-subtle" : "border-border-strong hover:border-accent/60 hover:bg-surface-hover"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            hidden
            onChange={(e) => validateAndSet(e.target.files?.[0])}
          />
          <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-surface-hover text-muted">
            <UploadCloud className="h-5 w-5" aria-hidden />
          </span>
          <p className="mt-3 text-sm font-medium text-content">Drop your document here</p>
          <p className="mt-0.5 text-xs text-muted">or click to browse</p>

          {file && (
            <div className="mt-4 flex w-full items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 text-left">
              <FileText className="h-4 w-4 shrink-0 text-accent" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium text-content">{file.name}</span>
                <span className="text-[11px] text-muted">
                  {formatBytes(file.size)} · PDF
                </span>
              </span>
            </div>
          )}

          {localError && <p className="mt-3 text-xs font-medium text-danger">{localError}</p>}
        </div>
      )}

      {progress && (busy || succeeded) && (
        <div className="py-1">
          <div className="flex items-center gap-3">
            <FileText className="h-4 w-4 shrink-0 text-accent" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-content">
              {progress.filename}
            </span>
            {succeeded && <CheckCircle2 className="h-4 w-4 shrink-0 text-positive" aria-hidden />}
          </div>

          <ol className="mt-4 space-y-2.5">
            {STAGE_STEPS.map((label, i) => {
              const active = busy && (progress.stage === "uploading" ? i === 0 : i <= 2);
              const complete = succeeded || (progress.stage === "processing" && i === 0);
              return (
                <li key={label} className="flex items-center gap-2.5 text-[13px]">
                  <span
                    className={`flex h-4 w-4 items-center justify-center rounded-full border text-[10px] ${
                      complete
                        ? "border-positive bg-positive text-white"
                        : active
                          ? "border-accent text-accent"
                          : "border-border text-faint"
                    }`}
                  >
                    {complete ? "✓" : active ? <Spinner /> : i + 1}
                  </span>
                  <span className={complete || active ? "text-content" : "text-faint"}>{label}</span>
                </li>
              );
            })}
          </ol>

          {succeeded && (
            <p className="mt-4 flex items-center gap-1.5 text-[13px] font-medium text-positive">
              <CheckCircle2 className="h-4 w-4" aria-hidden />
              Document ready
            </p>
          )}
        </div>
      )}

      {failed && progress && (
        <div className="py-1">
          <div className="flex items-start gap-2.5 rounded-lg border border-danger/30 bg-danger-subtle/60 px-3 py-3">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden />
            <div>
              <p className="text-[13px] font-medium text-danger">Unable to process this document</p>
              <p className="mt-0.5 text-xs text-muted">{progress.error}</p>
            </div>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={onClose}>
              Close
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setFile(null);
                onDone();
              }}
            >
              Try another file
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

function Spinner() {
  return <span className="block h-2 w-2 animate-spin rounded-full border border-current border-t-transparent" />;
}
