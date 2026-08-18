import type { WorkoutGarminData, WorkoutPlanRequest } from "../api/types";
import { isoDaysAgo, todayIso } from "./format";

/** State of the Garmin data-loading step of the Plan Workout survey. */
export type DataLoadState =
  | { status: "loading" }
  | { status: "done"; summary: WorkoutGarminData }
  | { status: "error"; message: string };

/** Everything the user has answered so far. Flat by design: the visible step
 * sequence is derived from it (see `visibleSteps`), never stored. */
export interface SurveyAnswers {
  mode?: "single" | "week";
  // Single-workout branch
  dayPreference?: "today" | "tomorrow" | "ai_pick";
  duration?: "30" | "45" | "60" | "90+";
  workoutType?: "easy" | "intervals" | "tempo" | "long_run" | "ai_decides";
  // Full-week branch
  sessionsPerWeek?: "3" | "4" | "5" | "6+";
  sessionDuration?: "30-45" | "45-60" | "60-90" | "mixed";
  weekChoice?: "this_week" | "next_week";
  // Garmin
  garminMode?: "chat_only" | "use_garmin";
  /** Set when the user opts to continue after "not connected" or a load error. */
  garminUnavailableChoice?: "continue_without";
  historyRange?: "week" | "month" | "90d" | "custom";
  customStart?: string;
  customEnd?: string;
  dataLoad?: DataLoadState;
  // Free text (committed on generate)
  description?: string;
}

export type StepId =
  | "mode"
  | "when"
  | "duration"
  | "type"
  | "sessions"
  | "sessionDuration"
  | "week"
  | "garmin"
  | "garminUnavailable"
  | "range"
  | "customRange"
  | "dataLoad"
  | "describe";

export interface ChipOption {
  value: string;
  label: string;
}

export interface Step {
  id: StepId;
  kind: "chips" | "dateRange" | "loading" | "freeText";
  prompt: string;
  answerKey?: keyof SurveyAnswers;
  options?: ChipOption[];
}

export const STEPS: Record<StepId, Step> = {
  mode: {
    id: "mode",
    kind: "chips",
    prompt: "Hi! Should I plan a single workout or a full training week?",
    answerKey: "mode",
    options: [
      { value: "single", label: "Single workout" },
      { value: "week", label: "Full training week" },
    ],
  },
  when: {
    id: "when",
    kind: "chips",
    prompt: "When do you want to run?",
    answerKey: "dayPreference",
    options: [
      { value: "today", label: "Today" },
      { value: "tomorrow", label: "Tomorrow" },
      { value: "ai_pick", label: "AI picks the best day" },
    ],
  },
  duration: {
    id: "duration",
    kind: "chips",
    prompt: "How long should the workout be?",
    answerKey: "duration",
    options: [
      { value: "30", label: "~30 min" },
      { value: "45", label: "~45 min" },
      { value: "60", label: "~60 min" },
      { value: "90+", label: "90+ min" },
    ],
  },
  type: {
    id: "type",
    kind: "chips",
    prompt: "What type of workout?",
    answerKey: "workoutType",
    options: [
      { value: "easy", label: "Easy run" },
      { value: "intervals", label: "Intervals" },
      { value: "tempo", label: "Tempo" },
      { value: "long_run", label: "Long run" },
      { value: "ai_decides", label: "Let the AI decide" },
    ],
  },
  sessions: {
    id: "sessions",
    kind: "chips",
    prompt: "How many sessions this week?",
    answerKey: "sessionsPerWeek",
    options: [
      { value: "3", label: "3" },
      { value: "4", label: "4" },
      { value: "5", label: "5" },
      { value: "6+", label: "6+" },
    ],
  },
  sessionDuration: {
    id: "sessionDuration",
    kind: "chips",
    prompt: "Typical session duration?",
    answerKey: "sessionDuration",
    options: [
      { value: "30-45", label: "30–45 min" },
      { value: "45-60", label: "45–60 min" },
      { value: "60-90", label: "60–90 min" },
      { value: "mixed", label: "Mixed — AI decides" },
    ],
  },
  week: {
    id: "week",
    kind: "chips",
    prompt: "Which week is this for?",
    answerKey: "weekChoice",
    options: [
      { value: "this_week", label: "This week" },
      { value: "next_week", label: "Next week" },
    ],
  },
  garmin: {
    id: "garmin",
    kind: "chips",
    prompt: "Should I base this on our chat alone, or also look at your Garmin data?",
    answerKey: "garminMode",
    options: [
      { value: "chat_only", label: "Chat only" },
      { value: "use_garmin", label: "Use my Garmin data" },
    ],
  },
  garminUnavailable: {
    id: "garminUnavailable",
    kind: "chips",
    prompt: "I couldn't find a connected Garmin device.",
    answerKey: "garminUnavailableChoice",
    options: [
      { value: "continue_without", label: "Continue without Garmin" },
      { value: "go_settings", label: "Go to Garmin settings →" },
    ],
  },
  range: {
    id: "range",
    kind: "chips",
    prompt: "How much history should I look at?",
    answerKey: "historyRange",
    options: [
      { value: "week", label: "Last week" },
      { value: "month", label: "Last month" },
      { value: "90d", label: "Last 90 days" },
      { value: "custom", label: "Custom range" },
    ],
  },
  customRange: {
    id: "customRange",
    kind: "dateRange",
    prompt: "Pick the date range to pull in.",
  },
  dataLoad: {
    id: "dataLoad",
    kind: "loading",
    prompt: "Syncing your Garmin data…",
  },
  describe: {
    id: "describe",
    kind: "freeText",
    prompt: "",
    answerKey: "description",
  },
};

export function describePrompt(mode: SurveyAnswers["mode"]): string {
  return mode === "week"
    ? "Almost there — describe what you want out of this training week."
    : "Almost there — describe what you want out of this workout.";
}

/** The concrete [start, end] the selected history range resolves to, if any. */
export function rangeForAnswers(
  a: SurveyAnswers,
): { start: string; end: string } | null {
  if (!a.historyRange) return null;
  if (a.historyRange === "custom") {
    if (!a.customStart || !a.customEnd || a.customStart > a.customEnd) return null;
    return { start: a.customStart, end: a.customEnd };
  }
  const days = a.historyRange === "week" ? 7 : a.historyRange === "month" ? 30 : 90;
  return { start: isoDaysAgo(days), end: todayIso() };
}

export function isAnswered(step: Step, a: SurveyAnswers): boolean {
  switch (step.id) {
    case "customRange":
      return rangeForAnswers(a) !== null;
    case "dataLoad":
      return (
        a.dataLoad?.status === "done" ||
        (a.dataLoad?.status === "error" && !!a.garminUnavailableChoice)
      );
    default:
      return step.answerKey !== undefined && a[step.answerKey] !== undefined;
  }
}

/** Derive the visible step sequence: every answered step plus the first
 * unanswered one. Branching falls out of the answers — no step counter. */
export function visibleSteps(a: SurveyAnswers, garminConnected: boolean): Step[] {
  const seq: Step[] = [STEPS.mode];
  if (a.mode === "single") seq.push(STEPS.when, STEPS.duration, STEPS.type);
  if (a.mode === "week") seq.push(STEPS.sessions, STEPS.sessionDuration, STEPS.week);
  if (a.mode) seq.push(STEPS.garmin);
  if (a.garminMode === "use_garmin") {
    if (!garminConnected) {
      seq.push(STEPS.garminUnavailable);
    } else {
      seq.push(STEPS.range);
      if (a.historyRange === "custom") seq.push(STEPS.customRange);
      if (rangeForAnswers(a)) seq.push(STEPS.dataLoad);
    }
  }
  seq.push(STEPS.describe);

  const visible: Step[] = [];
  for (const step of seq) {
    visible.push(step);
    if (!isAnswered(step, a)) break;
  }
  return visible;
}

/** The user-bubble label for an answered step. */
export function answerLabel(step: Step, a: SurveyAnswers): string {
  if (step.id === "customRange" && a.customStart && a.customEnd) {
    return `${a.customStart} – ${a.customEnd}`;
  }
  if (step.answerKey) {
    const value = a[step.answerKey];
    const option = step.options?.find((o) => o.value === value);
    if (option) return option.label;
    if (typeof value === "string") return value;
  }
  return "";
}

/** Rewind order: clearing a step also clears every downstream answer. */
const ANSWER_KEY_ORDER: (keyof SurveyAnswers)[] = [
  "mode",
  "dayPreference",
  "duration",
  "workoutType",
  "sessionsPerWeek",
  "sessionDuration",
  "weekChoice",
  "garminMode",
  "garminUnavailableChoice",
  "historyRange",
  "customStart",
  "customEnd",
  "dataLoad",
  "description",
];

const STEP_FIRST_KEY: Record<StepId, keyof SurveyAnswers> = {
  mode: "mode",
  when: "dayPreference",
  duration: "duration",
  type: "workoutType",
  sessions: "sessionsPerWeek",
  sessionDuration: "sessionDuration",
  week: "weekChoice",
  garmin: "garminMode",
  garminUnavailable: "garminUnavailableChoice",
  range: "historyRange",
  customRange: "customStart",
  dataLoad: "dataLoad",
  describe: "description",
};

export function rewoundAnswers(a: SurveyAnswers, stepId: StepId): SurveyAnswers {
  const from = ANSWER_KEY_ORDER.indexOf(STEP_FIRST_KEY[stepId]);
  const next: SurveyAnswers = {};
  for (const key of ANSWER_KEY_ORDER.slice(0, from)) {
    const value = a[key];
    if (value !== undefined) (next as Record<string, unknown>)[key] = value;
  }
  return next;
}

/** Shape the answers into the generate-endpoint request body. */
export function buildRequest(
  a: SurveyAnswers,
  aiModel: string | null,
  reasoningEffort: string | null,
): WorkoutPlanRequest {
  const garminActive = a.garminMode === "use_garmin" && a.dataLoad?.status === "done";
  const summary = garminActive && a.dataLoad?.status === "done" ? a.dataLoad.summary : null;
  return {
    mode: a.mode ?? "single",
    day_preference: a.dayPreference ?? null,
    duration: a.duration ?? null,
    workout_type: a.workoutType ?? null,
    sessions_per_week: a.sessionsPerWeek ?? null,
    session_duration: a.sessionDuration ?? null,
    week_choice: a.weekChoice ?? null,
    use_garmin: garminActive,
    garmin_start: summary?.start ?? null,
    garmin_end: summary?.end ?? null,
    description: a.description ?? "",
    ai_model: aiModel,
    reasoning_effort: reasoningEffort,
    client_today: todayIso(),
  };
}
