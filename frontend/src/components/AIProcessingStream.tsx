import { useCallback, useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Brain, ListChecks, ScrollText, Sparkles, Terminal, X } from "lucide-react";
import { streamAgent } from "../api/stream";
import { getTrace, saveTrace } from "../state/aiProcessingStore";
import type { AIProcessingEvent, AITrace, DoneEvent } from "../api/types";
import { Banner, Spinner } from "./ui";

const EMPTY_TRACE: AITrace = {
  prompt: undefined,
  thinking: "",
  text: "",
  steps: [],
  status: "running",
};

function applyEvent(t: AITrace, e: AIProcessingEvent): AITrace {
  switch (e.type) {
    case "prompt":
      return { ...t, prompt: { system: e.system, user: e.user } };
    case "thinking":
      return { ...t, thinking: t.thinking + e.delta };
    case "text":
      return { ...t, text: t.text + e.delta };
    case "step": {
      const last = t.steps[t.steps.length - 1];
      return last === e.label ? t : { ...t, steps: [...t.steps, e.label] };
    }
    default:
      return t;
  }
}

/**
 * Drives a live agent stream and exposes the accumulating trace plus modal
 * open-state. `run` streams an SSE endpoint; `replay` re-opens a stored trace.
 */
export function useAIProcessing() {
  const [trace, setTrace] = useState<AITrace>(EMPTY_TRACE);
  const [open, setOpen] = useState(false);
  const traceRef = useRef(trace);

  const commit = useCallback((next: AITrace) => {
    traceRef.current = next;
    setTrace(next);
  }, []);

  const run = useCallback(
    async (path: string, body?: unknown): Promise<DoneEvent> => {
      commit({ ...EMPTY_TRACE, steps: [], status: "running" });
      setOpen(true);
      try {
        const done = await streamAgent(path, body, (event) => {
          commit(applyEvent(traceRef.current, event));
        });
        const final: AITrace = { ...traceRef.current, status: "done" };
        commit(final);
        if (done.plan_id) saveTrace(done.plan_id, final);
        return done;
      } catch (err) {
        const message = err instanceof Error ? err.message : "AI processing failed.";
        commit({ ...traceRef.current, status: "error", error: message });
        throw err;
      }
    },
    [commit],
  );

  const replay = useCallback(
    (planId: number) => {
      const stored = getTrace(planId);
      if (stored) {
        commit(stored);
        setOpen(true);
      }
    },
    [commit],
  );

  return { trace, open, setOpen, run, replay };
}

function Pane({
  icon,
  title,
  body,
  empty,
  mono,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  empty: string;
  mono?: boolean;
}) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [body]);
  return (
    <div>
      <h3 className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {icon}
        {title}
      </h3>
      <pre
        ref={ref}
        className={`max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-700 ${
          mono ? "font-mono" : ""
        }`}
      >
        {body || <span className="text-slate-400">{empty}</span>}
      </pre>
    </div>
  );
}

/** Presentational modal that renders a (live or replayed) agent trace. */
export function AIProcessingModal({
  trace,
  open,
  onOpenChange,
}: {
  trace: AITrace;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[60] bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-[70] flex max-h-[90vh] w-[94vw] max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <Dialog.Title className="flex items-center gap-2 font-semibold text-slate-900">
              <Sparkles className="h-5 w-5 text-brand-600" /> AI processing
            </Dialog.Title>
            <Dialog.Close className="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
            <div className="flex items-center gap-2 text-sm">
              {trace.status === "running" && (
                <span className="flex items-center gap-2 text-brand-700">
                  <Spinner /> The coach is working…
                </span>
              )}
              {trace.status === "done" && (
                <span className="font-medium text-brand-700">Finished.</span>
              )}
              {trace.status === "error" && (
                <Banner kind="error">{trace.error ?? "Something went wrong."}</Banner>
              )}
            </div>

            {trace.steps.length > 0 && (
              <div>
                <h3 className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <ListChecks className="h-3.5 w-3.5" /> Steps
                </h3>
                <ul className="space-y-1 text-xs text-slate-600">
                  {trace.steps.map((s, i) => (
                    <li key={i} className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <Pane
              icon={<Brain className="h-3.5 w-3.5" />}
              title="Reasoning"
              body={trace.thinking}
              empty="No reasoning surfaced for this run."
            />
            <Pane
              icon={<ScrollText className="h-3.5 w-3.5" />}
              title="Response"
              body={trace.text}
              empty="Waiting for the coach's response…"
            />

            <details className="rounded-lg border border-slate-200">
              <summary className="flex cursor-pointer items-center gap-1.5 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700">
                <Terminal className="h-3.5 w-3.5" /> Full prompt
              </summary>
              <div className="space-y-3 px-3 pb-3">
                <Pane
                  icon={<span className="text-slate-400">system</span>}
                  title="System"
                  body={trace.prompt?.system ?? ""}
                  empty="—"
                  mono
                />
                <Pane
                  icon={<span className="text-slate-400">user</span>}
                  title="User"
                  body={trace.prompt?.user ?? ""}
                  empty="—"
                  mono
                />
              </div>
            </details>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
