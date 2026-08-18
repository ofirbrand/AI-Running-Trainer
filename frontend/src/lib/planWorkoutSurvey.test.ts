import { describe, expect, it } from "vitest";
import {
  type SurveyAnswers,
  buildRequest,
  rewoundAnswers,
  visibleSteps,
} from "./planWorkoutSurvey";

const last = <T,>(arr: T[]): T | undefined => arr[arr.length - 1];

const ids = (a: SurveyAnswers, connected = true) =>
  visibleSteps(a, connected).map((s) => s.id);

const singleBranch: SurveyAnswers = {
  mode: "single",
  dayPreference: "today",
  duration: "45",
  workoutType: "easy",
};

const doneLoad: SurveyAnswers["dataLoad"] = {
  status: "done",
  summary: { activities_count: 5, health_days: 12, start: "2026-07-19", end: "2026-08-18" },
};

describe("visibleSteps", () => {
  it("starts with only the mode question", () => {
    expect(ids({})).toEqual(["mode"]);
  });

  it("walks the single-workout branch in order", () => {
    expect(ids({ mode: "single" })).toEqual(["mode", "when"]);
    expect(ids({ mode: "single", dayPreference: "today" })).toEqual([
      "mode",
      "when",
      "duration",
    ]);
    expect(ids(singleBranch)).toEqual(["mode", "when", "duration", "type", "garmin"]);
  });

  it("walks the week branch in order", () => {
    expect(ids({ mode: "week" })).toEqual(["mode", "sessions"]);
    expect(
      ids({ mode: "week", sessionsPerWeek: "4", sessionDuration: "45-60", weekChoice: "this_week" }),
    ).toEqual(["mode", "sessions", "sessionDuration", "week", "garmin"]);
  });

  it("chat-only skips straight to the describe step", () => {
    expect(ids({ ...singleBranch, garminMode: "chat_only" })).toEqual([
      "mode",
      "when",
      "duration",
      "type",
      "garmin",
      "describe",
    ]);
  });

  it("shows the not-connected fallback when Garmin is disconnected", () => {
    const a: SurveyAnswers = { ...singleBranch, garminMode: "use_garmin" };
    expect(ids(a, false)).toEqual([
      "mode",
      "when",
      "duration",
      "type",
      "garmin",
      "garminUnavailable",
    ]);
    expect(ids({ ...a, garminUnavailableChoice: "continue_without" }, false)).toContain(
      "describe",
    );
  });

  it("connected Garmin flow: range → dataLoad → describe", () => {
    const a: SurveyAnswers = { ...singleBranch, garminMode: "use_garmin" };
    expect(last(ids(a))).toBe("range");
    expect(last(ids({ ...a, historyRange: "month" }))).toBe("dataLoad");
    expect(last(ids({ ...a, historyRange: "month", dataLoad: doneLoad }))).toBe("describe");
  });

  it("custom range inserts the date-range step and gates on valid dates", () => {
    const a: SurveyAnswers = { ...singleBranch, garminMode: "use_garmin", historyRange: "custom" };
    expect(last(ids(a))).toBe("customRange");
    // Inverted range does not resolve.
    expect(
      last(ids({ ...a, customStart: "2026-08-10", customEnd: "2026-08-01" })),
    ).toBe("customRange");
    expect(
      last(ids({ ...a, customStart: "2026-08-01", customEnd: "2026-08-10" })),
    ).toBe("dataLoad");
  });

  it("a load error blocks until the user opts to continue without Garmin", () => {
    const a: SurveyAnswers = {
      ...singleBranch,
      garminMode: "use_garmin",
      historyRange: "week",
      dataLoad: { status: "error", message: "expired" },
    };
    expect(last(ids(a))).toBe("dataLoad");
    expect(last(ids({ ...a, garminUnavailableChoice: "continue_without" }))).toBe("describe");
  });
});

describe("rewoundAnswers", () => {
  it("clears the tapped step and everything downstream", () => {
    const a: SurveyAnswers = {
      ...singleBranch,
      garminMode: "use_garmin",
      historyRange: "month",
      dataLoad: doneLoad,
      description: "something fun",
    };
    expect(rewoundAnswers(a, "garmin")).toEqual(singleBranch);
    expect(rewoundAnswers(a, "range")).toEqual({ ...singleBranch, garminMode: "use_garmin" });
    expect(rewoundAnswers(a, "mode")).toEqual({});
  });
});

describe("buildRequest", () => {
  it("sends the loaded Garmin range when data finished loading", () => {
    const body = buildRequest(
      {
        ...singleBranch,
        garminMode: "use_garmin",
        historyRange: "month",
        dataLoad: doneLoad,
        description: "shake out",
      },
      "claude-opus-4-8",
      "max",
    );
    expect(body.use_garmin).toBe(true);
    expect(body.garmin_start).toBe("2026-07-19");
    expect(body.garmin_end).toBe("2026-08-18");
    expect(body.ai_model).toBe("claude-opus-4-8");
    expect(body.reasoning_effort).toBe("max");
    expect(body.client_today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("drops Garmin fields for chat-only and continue-without flows", () => {
    const chatOnly = buildRequest(
      { ...singleBranch, garminMode: "chat_only", description: "x" },
      null,
      null,
    );
    expect(chatOnly.use_garmin).toBe(false);
    expect(chatOnly.garmin_start).toBeNull();

    const errored = buildRequest(
      {
        ...singleBranch,
        garminMode: "use_garmin",
        historyRange: "week",
        dataLoad: { status: "error", message: "boom" },
        garminUnavailableChoice: "continue_without",
        description: "x",
      },
      null,
      null,
    );
    expect(errored.use_garmin).toBe(false);
    expect(errored.garmin_start).toBeNull();
  });
});
