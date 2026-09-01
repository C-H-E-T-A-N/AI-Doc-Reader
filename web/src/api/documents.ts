import { api } from "./client";
import type { DeleteResponse, DocumentInfo, UploadResponse } from "@/types";

export function listDocuments(signal?: AbortSignal): Promise<DocumentInfo[]> {
  return api.get<DocumentInfo[]>("/documents", { signal, timeoutMs: 15_000 });
}

export function getDocument(documentId: string, signal?: AbortSignal): Promise<DocumentInfo> {
  return api.get<DocumentInfo>(`/documents/${encodeURIComponent(documentId)}`, { signal, timeoutMs: 15_000 });
}

/**
 * Upload a PDF and wait for the backend to extract, embed and index it.
 * Ingestion is synchronous server-side, so this single request covers the
 * whole pipeline — allow a generous timeout for large files.
 */
export function uploadDocument(file: File, signal?: AbortSignal): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file, file.name);
  return api.postForm<UploadResponse>("/documents/upload", form, { signal, timeoutMs: 180_000 });
}

export function deleteDocument(documentId: string, signal?: AbortSignal): Promise<DeleteResponse> {
  return api.delete<DeleteResponse>(`/documents/${encodeURIComponent(documentId)}`, { signal, timeoutMs: 20_000 });
}
