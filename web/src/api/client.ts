/**
 * Centralized HTTP client for the FastAPI backend.
 *
 * Base URL resolution (highest priority first):
 *   1. localStorage "aidr:apiBaseUrl"  — set at runtime via Settings
 *   2. import.meta.env.VITE_API_BASE_URL — baked in at build time
 *   3. http://127.0.0.1:8000            — local dev default
 *
 * No API keys or secrets ever live here — the browser only ever talks
 * to FastAPI, which owns every provider credential.
 */

const LS_KEY = "aidr:apiBaseUrl";
const BUILD_DEFAULT = import.meta.env.VITE_API_BASE_URL?.trim() || "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 60_000;

export function normalizeBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

export function getBaseUrl(): string {
  try {
    const stored = localStorage.getItem(LS_KEY);
    if (stored && stored.trim()) return normalizeBaseUrl(stored);
  } catch {
    /* localStorage blocked (private mode) — fall through to build default */
  }
  return normalizeBaseUrl(BUILD_DEFAULT);
}

export function setBaseUrl(url: string): string {
  const clean = normalizeBaseUrl(url) || normalizeBaseUrl(BUILD_DEFAULT);
  try {
    localStorage.setItem(LS_KEY, clean);
  } catch {
    /* ignore persistence failure */
  }
  return clean;
}

export function resetBaseUrl(): string {
  try {
    localStorage.removeItem(LS_KEY);
  } catch {
    /* ignore */
  }
  return normalizeBaseUrl(BUILD_DEFAULT);
}

export type ApiErrorKind = "network" | "timeout" | "http" | "parse";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;

  constructor(kind: ApiErrorKind, message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }

  /** A message safe and useful to show a user — never a stack trace. */
  get userMessage(): string {
    switch (this.kind) {
      case "network":
        return `Can't reach the AI service at ${getBaseUrl()}. Check that the backend is running.`;
      case "timeout":
        return "The request took too long and was cancelled. Please try again.";
      default:
        return this.message || "Something went wrong. Please try again.";
    }
  }
}

interface RequestOptions {
  method?: string;
  body?: BodyInit | null;
  headers?: Record<string, string>;
  timeoutMs?: number;
  signal?: AbortSignal;
  /** Skip JSON parsing and return the raw Response (for file downloads). */
  raw?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, headers, timeoutMs = DEFAULT_TIMEOUT_MS, signal, raw } = opts;

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(new DOMException("timeout", "TimeoutError")), timeoutMs);
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let res: Response;
  try {
    res = await fetch(`${getBaseUrl()}${path}`, { method, body, headers, signal: controller.signal });
  } catch (err) {
    window.clearTimeout(timer);
    if (err instanceof DOMException && (err.name === "TimeoutError" || err.name === "AbortError")) {
      // AbortError with our TimeoutError cause -> timeout; a caller abort -> rethrow as-is.
      if (signal?.aborted) throw err;
      throw new ApiError("timeout", "Request timed out.");
    }
    throw new ApiError("network", "Network request failed.");
  } finally {
    window.clearTimeout(timer);
  }

  if (raw) {
    if (!res.ok) throw await toHttpError(res);
    return res as unknown as T;
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      if (!res.ok) throw new ApiError("http", `Request failed (${res.status}).`, res.status);
      throw new ApiError("parse", "Received an unexpected response from the server.");
    }
  }

  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : `Request failed (${res.status}).`;
    throw new ApiError("http", detail, res.status);
  }

  return data as T;
}

async function toHttpError(res: Response): Promise<ApiError> {
  let detail = `Request failed (${res.status}).`;
  try {
    const body = await res.json();
    if (body && typeof body === "object" && "detail" in body) detail = String(body.detail);
  } catch {
    /* keep default */
  }
  return new ApiError("http", detail, res.status);
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => request<T>(path, { ...opts, method: "GET" }),
  delete: <T>(path: string, opts?: RequestOptions) => request<T>(path, { ...opts, method: "DELETE" }),
  postJson: <T>(path: string, payload: unknown, opts?: RequestOptions) =>
    request<T>(path, {
      ...opts,
      method: "POST",
      headers: { "Content-Type": "application/json", ...(opts?.headers ?? {}) },
      body: JSON.stringify(payload),
    }),
  postForm: <T>(path: string, form: FormData, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: "POST", body: form }),
  request,
};

/** Absolute URL for a document's original file (used for source previews). */
export function fileUrl(documentId: string): string {
  return `${getBaseUrl()}/documents/${encodeURIComponent(documentId)}/file`;
}
