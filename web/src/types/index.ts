/**
 * Types mirroring the FastAPI backend's response schemas
 * (see app/models/schemas.py) plus a few UI-only shapes.
 */

/** GET /documents  ->  DocumentInfo[]   (also the shape of GET /documents/{id}) */
export interface DocumentInfo {
  document_id: string;
  filename: string;
  file_type: string; // "pdf"
  size_bytes: number;
  pages: number;
  characters: number;
  chunks: number;
  uploaded_at: string; // ISO 8601
  status: string; // "indexed"
}

/** POST /documents/upload  ->  UploadResponse */
export interface UploadResponse {
  document_id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  pages: number;
  characters: number;
  chunks_indexed: number;
  uploaded_at: string;
  status: string;
}

/** POST /chat  request body */
export interface ChatRequestBody {
  question: string;
  document_id?: string;
}

/** One retrieved passage backing an answer. */
export interface Source {
  filename: string;
  page: number;
  text?: string | null;
  score?: number | null;
}

/** POST /chat  ->  ChatResponse */
export interface ChatResponse {
  answer: string;
  sources: Source[];
}

/** DELETE /documents/{id}  ->  DeleteResponse */
export interface DeleteResponse {
  document_id: string;
  status: string;
}

/* ----------------------------- UI-only ----------------------------- */

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  sources?: Source[];
  /** Answer came back but nothing relevant was found — a neutral state, not an error. */
  notFound?: boolean;
  /** The request itself failed. */
  errored?: boolean;
}

export type Theme = "light" | "dark";

/** Staged copy for the "AI is thinking" indicator. */
export type ThinkingStage = "searching" | "reading" | "generating";
