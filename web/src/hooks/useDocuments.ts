import { useCallback, useEffect, useRef, useState } from "react";
import { deleteDocument, listDocuments, uploadDocument } from "@/api/documents";
import { ApiError } from "@/api/client";
import type { DocumentInfo } from "@/types";

export interface UploadProgress {
  filename: string;
  /** Staged label shown in the modal while the request is in flight. */
  stage: "uploading" | "processing" | "done" | "error";
  error?: string;
}

interface UseDocumentsResult {
  documents: DocumentInfo[];
  selectedId: string | null;
  selected: DocumentInfo | null;
  loading: boolean;
  loadError: string | null;
  upload: UploadProgress | null;
  select: (id: string | null) => void;
  refresh: () => Promise<void>;
  uploadFile: (file: File) => Promise<DocumentInfo | null>;
  clearUpload: () => void;
  remove: (id: string) => Promise<void>;
  deletingId: string | null;
}

const UPLOAD_STAGE_DELAY = 1400;

export function useDocuments(): UseDocumentsResult {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadProgress | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const stageTimer = useRef<number>();

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const docs = await listDocuments();
      setDocuments(docs);
      setSelectedId((current) => {
        if (current && docs.some((d) => d.document_id === current)) return current;
        return docs[0]?.document_id ?? null;
      });
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.userMessage : "Failed to load documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => window.clearTimeout(stageTimer.current);
  }, [refresh]);

  const select = useCallback((id: string | null) => setSelectedId(id), []);
  const clearUpload = useCallback(() => setUpload(null), []);

  const uploadFile = useCallback<UseDocumentsResult["uploadFile"]>(async (file) => {
    window.clearTimeout(stageTimer.current);
    setUpload({ filename: file.name, stage: "uploading" });
    // The backend does extract -> chunk -> embed -> index in one call; we
    // can't observe those sub-steps, so advance the label on a timer to
    // reflect that processing is under way.
    stageTimer.current = window.setTimeout(
      () => setUpload((u) => (u && u.stage === "uploading" ? { ...u, stage: "processing" } : u)),
      UPLOAD_STAGE_DELAY,
    );

    try {
      const res = await uploadDocument(file);
      window.clearTimeout(stageTimer.current);
      setUpload({ filename: file.name, stage: "done" });
      const docs = await listDocuments().catch(() => null);
      let created: DocumentInfo | null = null;
      if (docs) {
        setDocuments(docs);
        created = docs.find((d) => d.document_id === res.document_id) ?? null;
      }
      if (!created) {
        created = {
          document_id: res.document_id,
          filename: res.filename,
          file_type: res.file_type,
          size_bytes: res.size_bytes,
          pages: res.pages,
          characters: res.characters,
          chunks: res.chunks_indexed,
          uploaded_at: res.uploaded_at,
          status: res.status,
        };
        setDocuments((prev) => [created as DocumentInfo, ...prev]);
      }
      setSelectedId(res.document_id);
      return created;
    } catch (err) {
      window.clearTimeout(stageTimer.current);
      const message =
        err instanceof ApiError
          ? err.status === 422
            ? "This PDF couldn't be read. It may be scanned images or password-protected."
            : err.userMessage
          : "Unable to process this document.";
      setUpload({ filename: file.name, stage: "error", error: message });
      return null;
    }
  }, []);

  const remove = useCallback<UseDocumentsResult["remove"]>(
    async (id) => {
      setDeletingId(id);
      try {
        await deleteDocument(id);
        setDocuments((prev) => {
          const next = prev.filter((d) => d.document_id !== id);
          setSelectedId((current) => (current === id ? (next[0]?.document_id ?? null) : current));
          return next;
        });
      } catch (err) {
        setLoadError(err instanceof ApiError ? err.userMessage : "Failed to delete the document.");
        throw err;
      } finally {
        setDeletingId(null);
      }
    },
    [],
  );

  const selected = documents.find((d) => d.document_id === selectedId) ?? null;

  return {
    documents,
    selectedId,
    selected,
    loading,
    loadError,
    upload,
    select,
    refresh,
    uploadFile,
    clearUpload,
    remove,
    deletingId,
  };
}
