import { useMemo } from "react";
import clsx from "clsx";
import type { PlannedWorkout, PlanVersion } from "../api/types";
import { formatShortDate } from "../lib/format";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function keyFor(pw: PlannedWorkout): string {
  return `${pw.workout_type}|${pw.goal ?? ""}`;
}

function groupByWeek(version: PlanVersion): Map<number, Map<number, PlannedWorkout[]>> {
  const weeks = new Map<number, Map<number, PlannedWorkout[]>>();
  for (const pw of version.planned_workouts) {
    if (!weeks.has(pw.week_no)) weeks.set(pw.week_no, new Map());
    const wk = weeks.get(pw.week_no)!;
    if (!wk.has(pw.weekday)) wk.set(pw.weekday, []);
    wk.get(pw.weekday)!.push(pw);
  }
  return weeks;
}

/** Side-by-side comparison: current (left) vs proposed (right). */
export function PlanDiff({
  left,
  right,
  leftTitle = "Current plan",
  rightTitle = "Proposed plan",
}: {
  left: PlanVersion;
  right: PlanVersion;
  leftTitle?: string;
  rightTitle?: string;
}) {
  const leftWeeks = useMemo(() => groupByWeek(left), [left]);
  const rightWeeks = useMemo(() => groupByWeek(right), [right]);
  const allWeeks = useMemo(() => {
    const s = new Set<number>([...leftWeeks.keys(), ...rightWeeks.keys()]);
    return [...s].sort((a, b) => a - b);
  }, [leftWeeks, rightWeeks]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <h4 className="text-sm font-semibold text-slate-500">{leftTitle}</h4>
        <h4 className="text-sm font-semibold text-brand-700">{rightTitle}</h4>
      </div>
      {allWeeks.map((wk) => (
        <div key={wk} className="grid grid-cols-2 gap-4">
          <WeekColumn week={wk} days={leftWeeks.get(wk)} compareTo={rightWeeks.get(wk)} side="left" />
          <WeekColumn week={wk} days={rightWeeks.get(wk)} compareTo={leftWeeks.get(wk)} side="right" />
        </div>
      ))}
    </div>
  );
}

function WeekColumn({
  week,
  days,
  compareTo,
  side,
}: {
  week: number;
  days?: Map<number, PlannedWorkout[]>;
  compareTo?: Map<number, PlannedWorkout[]>;
  side: "left" | "right";
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="mb-2 text-xs font-semibold text-slate-400">Week {week}</p>
      <div className="space-y-1">
        {DAYS.map((label, day) => {
          const here = days?.get(day) ?? [];
          const there = compareTo?.get(day) ?? [];
          const changed = isChanged(here, there);
          return (
            <div
              key={day}
              className={clsx(
                "flex gap-2 rounded px-2 py-1 text-xs",
                changed &&
                  (side === "right" ? "bg-brand-50" : "bg-amber-50/60"),
              )}
            >
              <span className="w-8 shrink-0 font-medium text-slate-400">{label}</span>
              <div className="flex-1">
                {here.length === 0 ? (
                  <span className="text-slate-300">Rest</span>
                ) : (
                  here.map((pw) => (
                    <div key={pw.id}>
                      <span className="font-medium text-slate-700">{pw.workout_type}</span>
                      {pw.goal && <span className="text-slate-500"> — {pw.goal}</span>}
                      <span className="ml-1 text-[10px] text-slate-300">
                        {formatShortDate(pw.date)}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function isChanged(a: PlannedWorkout[], b: PlannedWorkout[]): boolean {
  const sa = a.map(keyFor).sort().join("~");
  const sb = b.map(keyFor).sort().join("~");
  return sa !== sb;
}
