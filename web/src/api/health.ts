import { api, ApiError } from "./client";

export type ConnectionState = "checking" | "online" | "offline";

export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await api.get<{ status?: string }>("/health", { signal, timeoutMs: 8_000 });
    return res?.status === "ok";
  } catch (err) {
    if (err instanceof ApiError) return false;
    throw err;
  }
}
