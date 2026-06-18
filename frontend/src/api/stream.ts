import { getToken } from "./client";
import type { AIProcessingEvent, DoneEvent } from "./types";

/**
 * POST to an SSE endpoint and invoke `onEvent` for each streamed event.
 *
 * Uses `fetch` + `ReadableStream` rather than `EventSource` because the API is
 * bearer-authenticated and `EventSource` cannot send an `Authorization` header.
 * Resolves with the terminal `done` event; rejects on an `error` event, a
 * non-2xx response, or a stream that ends without completing.
 */
export async function streamAgent(
  path: string,
  body: unknown,
  onEvent: (event: AIProcessingEvent) => void,
): Promise<DoneEvent> {
  const token = getToken();
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body ?? {}),
  });

  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status}).`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* non-JSON body — keep the generic message */
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let done: DoneEvent | null = null;

  const handleFrame = (frame: string) => {
    const line = frame.split("\n").find((l) => l.startsWith("data:"));
    if (!line) return;
    const payload = line.slice(5).trim();
    if (!payload) return;
    const event = JSON.parse(payload) as AIProcessingEvent;
    if (event.type === "error") {
      throw new Error(event.message || "AI processing failed.");
    }
    onEvent(event);
    if (event.type === "done") done = event;
  };

  for (;;) {
    const { value, done: finished } = await reader.read();
    if (finished) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      handleFrame(frame);
    }
  }
  // Flush any trailing frame not terminated by a blank line.
  if (buffer.trim()) handleFrame(buffer);

  if (!done) throw new Error("The stream ended before the plan was ready.");
  return done;
}
