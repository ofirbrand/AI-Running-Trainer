import { useMemo } from "react";
import clsx from "clsx";
import type { PlannedWorkout, PlanVersion } from "../api/types";
import { InfoTip } from "./InfoTip";
import { formatShortDate } from "../lib/format";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function typeColor(type: string): string {
  const t = type.toLowerCase();
  if (t.includes("rest")) return "bg-slate-50 text-slate-400 border-slate-100";
  if (t.includes("long")) return "bg-purple-50 text-purple-700 border-purple-100";
  if (t.includes("tempo") || t.includes("threshold"))
    return "bg-amber-50 text-amber-800 border-amber-100";
  if (t.includes("interval") || t.includes("vo2") || t.includes("speed"))
    return "bg-red-50 text-red-700 border-red-100";
  if (t.includes("recovery")) return "bg-sky-50 text-sky-700 border-sky-100";
  if (t.includes("strength") || t.includes("gym"))
    return "bg-indigo-50 text-indigo-700 border-indigo-100";
  return "bg-brand-50 text-brand-800 border-brand-100";
}

interface WeekGroup {
  week_no: number;
  byDay: Record<number, PlannedWorkout[]>;
}

export function WeeklyTable({ version }: { version: PlanVersion }) {
  const weeks = useMemo<WeekGroup[]>(() => {
    const map = new Map<number, WeekGroup>();
    for (const pw of version.planned_workouts) {
      if (!map.has(pw.week_no)) map.set(pw.week_no, { week_no: pw.week_no, byDay: {} });
      const g = map.get(pw.week_no)!;
      (g.byDay[pw.weekday] ??= []).push(pw);
    }
    return [...map.values()].sort((a, b) => a.week_no - b.week_no);
  }, [version]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] border-separate border-spacing-1">
        <thead>
          <tr>
            <th className="w-16 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
              Week
            </th>
            {DAYS.map((d) => (
              <th
                key={d}
                className="text-center text-xs font-semibold uppercase tracking-wide text-slate-400"
              >
                {d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week) => (
            <tr key={week.week_no}>
              <td className="align-top text-sm font-semibold text-slate-500">
                {week.week_no}
              </td>
              {DAYS.map((_, day) => {
                const workouts = week.byDay[day] ?? [];
                return (
                  <td key={day} className="align-top">
                    <div className="flex h-full flex-col gap-1">
                      {workouts.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-slate-100 px-2 py-3 text-center text-[11px] text-slate-300">
                          Rest
                        </div>
                      ) : (
                        workouts.map((w) => <WorkoutCell key={w.id} workout={w} />)
                      )}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function WorkoutCell({ workout }: { workout: PlannedWorkout }) {
  const howTo =
    [workout.goal, workout.how_to].filter(Boolean).join("\n\n") || "No extra details.";
  return (
    <div className={clsx("rounded-lg border px-2 py-1.5 text-left", typeColor(workout.workout_type))}>
      <div className="flex items-center justify-between gap-1">
        <span className="text-[11px] font-semibold leading-tight">{workout.workout_type}</span>
        <InfoTip text={howTo} label={`How to: ${workout.workout_type}`} />
      </div>
      {workout.goal && (
        <p className="mt-0.5 line-clamp-2 text-[11px] leading-tight opacity-80">{workout.goal}</p>
      )}
      <p className="mt-0.5 text-[10px] opacity-60">{formatShortDate(workout.date)}</p>
    </div>
  );
}
