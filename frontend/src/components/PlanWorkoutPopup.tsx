import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import clsx from "clsx";
import { AlertTriangle, Check, Sparkles, X } from "lucide-react";
import { garminApi, workoutPlannerApi } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import type { PlanVersion } from "../api/types";
import {
  type Step,
  type SurveyAnswers,
  answerLabel,
  buildRequest,
  describePrompt,
  isAnswered,
  rangeForAnswers,
  rewoundAnswers,
  visibleSteps,
} from "../lib/planWorkoutSurvey";
import { formatShortDate, todayIso } from "../lib/format";
import { AIProcessingModal, useAIProcessing } from "./AIProcessingStream";
import { ModelEffortPicker } from "./ModelEffortPicker";
import { Spinner } from "./ui";
import { WeeklyTable } from "./WeeklyTable";

function BotBubble({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "warning" }) {
  return (
    <div className="flex justify-start">
      <div
        className={clsx(
          "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm",
          tone === "warning" ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-700",
        )}
      >
        {children}
      </div>
    </div>
  );
}

function Chips({
  options,
  onChoose,
  disabled,
}: {
  options: { value: string; label: string }[];
  onChoose: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap justify-start gap-2 pl-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          disabled={disabled}
          onClick={() => onChoose(o.value)}
          className="rounded-full border border-brand-300 bg-white px-4 py-2 text-sm font-medium text-brand-700 transition-colors hover:bg-brand-50 active:bg-brand-100 disabled:opacity-50"
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/**
 * "Plan Workout": a scripted survey rendered as a chat, ending in ONE AI call.
 * The generated workout/week is transient — rendered here, never saved, and
 * closing with a result requires confirming that it will be discarded.
 */
export function PlanWorkoutPopup({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const ai = useAIProcessing();
  const { data: garmin } = useQuery({ queryKey: ["garmin-status"], queryFn: garminApi.status });
  const garminConnected = !!garmin?.connected;

  const [answers, setAnswers] = useState<SurveyAnswers>({});
  const [draft, setDraft] = useState("");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [aiModel, setAiModel] = useState<string | null>(null);
  const [effort, setEffort] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [result, setResult] = useState<PlanVersion | null>(null);
  const [confirmingClose, setConfirmingClose] = useState(false);

  const steps = visibleSteps(answers, garminConnected);
  const active = steps[steps.length - 1];
  const describeActive = active?.id === "describe" && !isAnswered(active, answers);
  const busy = generating || answers.dataLoad?.status === "loading";
  const mustConfirm = result !== null;

  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [answers, generating, genError]);

  // The data-loading step: fresh-sync the selected range exactly once.
  useEffect(() => {
    if (!open || active?.id !== "dataLoad" || answers.dataLoad !== undefined) return;
    const range = rangeForAnswers(answers);
    if (!range) return;
    setAnswers((a) => ({ ...a, dataLoad: { status: "loading" } }));
    workoutPlannerApi
      .loadGarminData(range.start, range.end)
      .then((summary) =>
        setAnswers((a) => ({ ...a, dataLoad: { status: "done", summary } })),
      )
      .catch((err) =>
        setAnswers((a) => ({
          ...a,
          dataLoad: {
            status: "error",
            message: apiErrorMessage(err, "Couldn't load your Garmin data."),
          },
        })),
      );
  }, [open, active?.id, answers]);

  function goToGarminSettings() {
    onOpenChange(false);
    navigate("/profile");
  }

  function choose(step: Step, value: string) {
    if (busy) return;
    setGenError(null);
    if (value === "go_settings") {
      goToGarminSettings();
      return;
    }
    if (!step.answerKey) return;
    setAnswers((a) => ({ ...a, [step.answerKey as string]: value }));
  }

  function rewindTo(step: Step) {
    if (busy) return;
    setGenError(null);
    setAnswers((a) => rewoundAnswers(a, step.id));
  }

  function confirmCustomRange() {
    if (!customStart || !customEnd || customStart > customEnd) return;
    setAnswers((a) => ({ ...a, customStart, customEnd }));
  }

  async function generate() {
    const description = draft.trim();
    if (!description || generating) return;
    setGenerating(true);
    setGenError(null);
    setAnswers((a) => ({ ...a, description }));
    try {
      const done = await ai.run(
        "/workout-planner/generate",
        buildRequest({ ...answers, description }, aiModel, effort),
      );
      if (!done.workout_plan) throw new Error("The AI did not return a workout plan.");
      setResult(done.workout_plan.version);
      setDraft("");
      ai.setOpen(false);
    } catch (err) {
      setGenError(err instanceof Error ? err.message : "Workout generation failed.");
      setAnswers((a) => ({ ...a, description: undefined }));
    } finally {
      setGenerating(false);
    }
  }

  function requestClose() {
    if (mustConfirm) setConfirmingClose(true);
    else onOpenChange(false);
  }

  function discardAndClose() {
    setResult(null);
    setAnswers({});
    setDraft("");
    setCustomStart("");
    setCustomEnd("");
    setConfirmingClose(false);
    onOpenChange(false);
  }

  function renderStep(step: Step) {
    const answered = isAnswered(step, answers);
    const isActive = step.id === active?.id;

    if (step.id === "dataLoad") {
      const load = answers.dataLoad;
      return (
        <div key={step.id} className="space-y-2">
          {(!load || load.status === "loading") && (
            <BotBubble>
              <span className="flex items-center gap-2">
                <Spinner /> Syncing your Garmin data…
              </span>
            </BotBubble>
          )}
          {load?.status === "done" && (
            <BotBubble>
              <span className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                <span>
                  Loaded {load.summary.activities_count} activities and{" "}
                  {load.summary.health_days} days of health data (
                  {formatShortDate(load.summary.start)} –{" "}
                  {formatShortDate(load.summary.end)}).
                </span>
              </span>
            </BotBubble>
          )}
          {load?.status === "error" && (
            <>
              <BotBubble tone="warning">
                <span className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{load.message}</span>
                </span>
              </BotBubble>
              {answers.garminUnavailableChoice ? (
                <UserBubble onRewind={() => rewindTo(step)} disabled={busy}>
                  Continue without Garmin
                </UserBubble>
              ) : (
                <Chips
                  disabled={busy}
                  options={[
                    { value: "continue_without", label: "Continue without Garmin" },
                    { value: "go_settings", label: "Go to Garmin settings →" },
                  ]}
                  onChoose={(v) =>
                    v === "go_settings"
                      ? goToGarminSettings()
                      : setAnswers((a) => ({ ...a, garminUnavailableChoice: "continue_without" }))
                  }
                />
              )}
            </>
          )}
        </div>
      );
    }

    if (step.id === "customRange") {
      return (
        <div key={step.id} className="space-y-2">
          <BotBubble>{step.prompt}</BotBubble>
          {answered ? (
            <UserBubble onRewind={() => rewindTo(step)} disabled={busy}>
              {answerLabel(step, answers)}
            </UserBubble>
          ) : (
            <div className="flex flex-wrap items-end gap-2 pl-1">
              <label className="text-xs text-slate-500">
                From
                <input
                  type="date"
                  className="input mt-1"
                  value={customStart}
                  max={customEnd || todayIso()}
                  onChange={(e) => setCustomStart(e.target.value)}
                />
              </label>
              <label className="text-xs text-slate-500">
                To
                <input
                  type="date"
                  className="input mt-1"
                  value={customEnd}
                  min={customStart || undefined}
                  max={todayIso()}
                  onChange={(e) => setCustomEnd(e.target.value)}
                />
              </label>
              <button
                type="button"
                className="btn-secondary"
                disabled={!customStart || !customEnd || customStart > customEnd}
                onClick={confirmCustomRange}
              >
                Use this range
              </button>
            </div>
          )}
        </div>
      );
    }

    const prompt = step.id === "describe" ? describePrompt(answers.mode) : step.prompt;
    return (
      <div key={step.id} className="space-y-2">
        <BotBubble tone={step.id === "garminUnavailable" ? "warning" : "default"}>
          {prompt}
        </BotBubble>
        {answered ? (
          <UserBubble
            onRewind={step.id === "describe" ? undefined : () => rewindTo(step)}
            disabled={busy}
          >
            {answerLabel(step, answers)}
          </UserBubble>
        ) : (
          isActive &&
          step.kind === "chips" &&
          step.options && <Chips options={step.options} onChoose={(v) => choose(step, v)} disabled={busy} />
        )}
      </div>
    );
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        // Escape / overlay-click land here: once a result exists, closing
        // requires an explicit confirmation (the result is never saved).
        if (!next && mustConfirm) {
          setConfirmingClose(true);
          return;
        }
        onOpenChange(next);
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content
          className={clsx(
            "fixed inset-0 z-50 flex flex-col bg-white shadow-xl sm:inset-auto sm:left-1/2 sm:top-1/2 sm:max-h-[90vh] sm:w-[92vw] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl",
            result ? "sm:max-w-4xl" : "sm:h-[600px] sm:max-w-lg",
          )}
        >
          <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-5 pb-4 pt-[calc(1rem_+_env(safe-area-inset-top))] sm:pt-4">
            <Dialog.Title className="flex items-center gap-2 font-semibold text-slate-900">
              <Sparkles className="h-5 w-5 text-brand-600" />
              {result ? "Your workout plan" : "Plan Workout"}
            </Dialog.Title>
            <div className="flex items-center gap-2">
              {!result && (
                <ModelEffortPicker
                  model={aiModel}
                  effort={effort}
                  disabled={generating}
                  onChange={(m, e) => {
                    setAiModel(m);
                    setEffort(e);
                  }}
                />
              )}
              <button
                type="button"
                onClick={requestClose}
                className="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {result ? (
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
              <div className="card space-y-2 p-4">
                <h3 className="text-sm font-semibold text-slate-800">Coach's explanation</h3>
                <p className="whitespace-pre-wrap text-sm text-slate-600">
                  {result.structure_explanation}
                </p>
                {result.full_explanation && (
                  <details className="text-sm text-slate-600">
                    <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-400">
                      Full coaching rationale
                    </summary>
                    <p className="mt-2 whitespace-pre-wrap">{result.full_explanation}</p>
                  </details>
                )}
              </div>
              <WeeklyTable version={result} />
              <p className="text-xs text-slate-400">
                This workout isn't saved — it lives only in this window.
              </p>
            </div>
          ) : (
            <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
              {steps.map(renderStep)}
              {generating && (
                <BotBubble>
                  <span className="flex items-center gap-2">
                    <Spinner /> The coach is working on it…
                  </span>
                </BotBubble>
              )}
            </div>
          )}

          {result ? (
            <div className="border-t border-slate-200 px-5 pt-3 pb-[calc(0.75rem_+_env(safe-area-inset-bottom))] sm:pb-3">
              {confirmingClose ? (
                <div className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="flex items-center gap-2 text-sm text-amber-800">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    Closing will discard this workout — it isn't saved anywhere.
                  </p>
                  <div className="flex shrink-0 gap-2">
                    <button className="btn-secondary" onClick={() => setConfirmingClose(false)}>
                      Keep viewing
                    </button>
                    <button className="btn-danger" onClick={discardAndClose}>
                      Discard and close
                    </button>
                  </div>
                </div>
              ) : (
                <button className="btn-secondary w-full sm:w-auto" onClick={requestClose}>
                  Close
                </button>
              )}
            </div>
          ) : (
            describeActive && (
              <div className="border-t border-slate-200 px-5 pt-3 pb-[calc(0.75rem_+_env(safe-area-inset-bottom))] sm:pb-3">
                {genError && <div className="pb-2 text-sm text-red-600">{genError}</div>}
                <div className="flex items-end gap-2">
                  <textarea
                    className="input min-h-[44px] resize-none"
                    rows={2}
                    placeholder={
                      answers.mode === "week"
                        ? "e.g. Building toward a 10K — keep one hard session…"
                        : "e.g. Something to shake out tired legs…"
                    }
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        void generate();
                      }
                    }}
                  />
                  <button
                    className="btn-primary h-[44px] shrink-0"
                    onClick={() => void generate()}
                    disabled={generating || !draft.trim()}
                  >
                    {generating ? <Spinner /> : <Sparkles className="h-4 w-4" />} Generate
                  </button>
                </div>
              </div>
            )
          )}
        </Dialog.Content>
      </Dialog.Portal>

      <AIProcessingModal trace={ai.trace} open={ai.open} onOpenChange={ai.setOpen} />
    </Dialog.Root>
  );
}

function UserBubble({
  children,
  onRewind,
  disabled,
}: {
  children: React.ReactNode;
  onRewind?: () => void;
  disabled?: boolean;
}) {
  const classes =
    "max-w-[80%] whitespace-pre-wrap rounded-2xl bg-brand-600 px-4 py-2 text-left text-sm text-white";
  return (
    <div className="flex justify-end">
      {onRewind ? (
        <button
          type="button"
          title="Tap to change"
          disabled={disabled}
          onClick={onRewind}
          className={clsx(classes, "transition-shadow hover:ring-2 hover:ring-brand-300 disabled:opacity-70")}
        >
          {children}
        </button>
      ) : (
        <div className={classes}>{children}</div>
      )}
    </div>
  );
}
