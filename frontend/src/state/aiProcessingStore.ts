import { useSyncExternalStore } from "react";
import type { AITrace } from "../api/types";

/**
 * Session-only, in-memory store of the most recent agent trace per plan.
 * Survives SPA navigation; cleared on a full page reload (no persistence by
 * design). Backs the "View AI processing" button on the plan page.
 */
const traces = new Map<number, AITrace>();
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function saveTrace(planId: number, trace: AITrace) {
  traces.set(planId, trace);
  emit();
}

export function getTrace(planId: number): AITrace | undefined {
  return traces.get(planId);
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** Reactive flag: is a completed trace available for this plan? */
export function useHasTrace(planId: number): boolean {
  return useSyncExternalStore(
    subscribe,
    () => traces.has(planId),
    () => false,
  );
}
