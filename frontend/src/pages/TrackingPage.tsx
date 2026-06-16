import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, CircleCheck, CircleDashed, CircleX } from "lucide-react";
import { plansApi } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { Badge, Banner, PageLoader } from "../components/ui";
import { InfoTip } from "../components/InfoTip";
import { formatDistance, formatDuration, formatPace, formatShortDate } from "../lib/format";
import type { TrackingDay, TrackingStatus } from "../api/types";

function StatusBadge({ status }: { status: TrackingStatus }) {
  const map: Record<TrackingStatus, { color: Parameters<typeof Badge>[0]["color"]; label: string; icon: JSX.Element }> = {
    completed: { color: "green", label: "Completed", icon: <CircleCheck className="h-3.5 w-3.5" /> },
    missed: { color: "red", label: "Missed", icon: <CircleX className="h-3.5 w-3.5" /> },
    upcoming: { color: "blue", label: "Upcoming", icon: <CircleDashed className="h-3.5 w-3.5" /> },
    extra: { color: "purple", label: "Extra", icon: <CircleCheck className="h-3.5 w-3.5" /> },
    rest: { color: "slate", label: "Rest", icon: <CircleDashed className="h-3.5 w-3.5" /> },
  };
  const cfg = map[status];
  return (
    <Badge color={cfg.color}>
      <span className="flex items-center gap-1">
        {cfg.icon}
        {cfg.label}
      </span>
    </Badge>
  );
}

function DayRow({ day }: { day: TrackingDay }) {
  return (
    <tr className="border-b border-slate-100 last:border-0">
      <td className="py-3 pr-3 align-top">
        <p className="font-medium text-slate-700">{day.weekday_name}</p>
        <p className="text-xs text-slate-400">{formatShortDate(day.date)}</p>
      </td>
      <td className="py-3 pr-3 align-top">
        {day.planned.length === 0 ? (
          <span className="text-sm text-slate-300">Rest day</span>
        ) : (
          <div className="space-y-1.5">
            {day.planned.map((p) => (
              <div key={p.id} className="text-sm">
                <span className="flex items-center gap-1 font-medium text-slate-700">
                  {p.workout_type}
                  <InfoTip
                    text={[p.goal, p.how_to].filter(Boolean).join("\n\n") || "No extra details."}
                  />
                </span>
                {p.goal && <p className="text-xs text-slate-500">{p.goal}</p>}
              </div>
            ))}
          </div>
        )}
      </td>
      <td className="py-3 pr-3 align-top">
        {day.actual.length === 0 ? (
          <span className="text-sm text-slate-300">—</span>
        ) : (
          <div className="space-y-1.5">
            {day.actual.map((a) => (
              <div key={a.id} className="text-sm text-slate-700">
                <p className="font-medium">{a.name || a.activity_type || "Activity"}</p>
                <p className="text-xs text-slate-500">
                  {formatDistance(a.distance_m)} · {formatDuration(a.duration_s)} ·{" "}
                  {formatPace(a.avg_pace_s_per_km)}
                </p>
              </div>
            ))}
          </div>
        )}
      </td>
      <td className="py-3 align-top">
        <StatusBadge status={day.status} />
      </td>
    </tr>
  );
}

export function TrackingPage() {
  const { id } = useParams();
  const planId = Number(id);
  const [weekNo, setWeekNo] = useState<number | undefined>(undefined);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["tracking", planId, weekNo],
    queryFn: () => plansApi.tracking(planId, weekNo),
  });

  if (isLoading) return <PageLoader />;
  if (isError)
    return (
      <div className="space-y-4">
        <Banner kind="error">{apiErrorMessage(error)}</Banner>
        <Link to={`/plans/${planId}`} className="btn-secondary">
          View plan
        </Link>
      </div>
    );
  if (!data) return null;

  const current = data.week_no;
  const canPrev = current > 1;
  const canNext = current < data.num_weeks;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Progress tracking</h1>
          <p className="text-sm text-slate-500">
            Week {data.week_no} of {data.num_weeks}
            {data.week_no === data.current_week && " · current week"}
          </p>
        </div>
        <Link to={`/plans/${planId}`} className="btn-secondary">
          View full plan
        </Link>
      </div>

      <div className="card p-6">
        <div className="mb-4 flex items-center justify-between">
          <button
            className="btn-ghost"
            onClick={() => setWeekNo(Math.max(1, current - 1))}
            disabled={!canPrev}
          >
            <ChevronLeft className="h-4 w-4" /> Previous
          </button>
          <p className="text-sm font-medium text-slate-600">
            {formatShortDate(data.week_start)} – {formatShortDate(data.week_end)}
          </p>
          <div className="flex gap-2">
            {data.week_no !== data.current_week && (
              <button className="btn-ghost" onClick={() => setWeekNo(undefined)}>
                Current week
              </button>
            )}
            <button
              className="btn-ghost"
              onClick={() => setWeekNo(Math.min(data.num_weeks, current + 1))}
              disabled={!canNext}
            >
              Next <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
                <th className="pb-2 pr-3">Day</th>
                <th className="pb-2 pr-3">Planned</th>
                <th className="pb-2 pr-3">Actual</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.days.map((day) => (
                <DayRow key={day.date} day={day} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
