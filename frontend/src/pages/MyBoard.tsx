import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity as ActivityIcon,
  CalendarSearch,
  Gauge,
  HeartPulse,
  RefreshCw,
  Timer,
  Watch,
} from "lucide-react";
import { garminApi } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { ActivityDetailModal } from "../components/ActivityDetailModal";
import { Badge, Banner, PageLoader, Spinner } from "../components/ui";
import {
  formatDate,
  formatDistance,
  formatDuration,
  formatPace,
  titleCase,
} from "../lib/format";
import type { ActivitySummary } from "../api/types";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function ActivityCard({
  activity,
  highlight = false,
  onSelect,
}: {
  activity: ActivitySummary;
  highlight?: boolean;
  onSelect?: (id: number) => void;
}) {
  const base = highlight
    ? "rounded-xl border border-brand-200 bg-brand-50/40 p-5"
    : "card p-5";
  const clickable = onSelect
    ? "cursor-pointer transition-shadow hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brand-200"
    : "";
  return (
    <div
      className={`${base} ${clickable}`}
      {...(onSelect
        ? {
            role: "button",
            tabIndex: 0,
            onClick: () => onSelect(activity.id),
            onKeyDown: (e: React.KeyboardEvent) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(activity.id);
              }
            },
          }
        : {})}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-slate-900">
              {activity.name || titleCase(activity.activity_type) || "Activity"}
            </h3>
            {activity.activity_type && (
              <Badge color="green">{titleCase(activity.activity_type)}</Badge>
            )}
          </div>
          <p className="text-sm text-slate-500">{formatDate(activity.activity_date)}</p>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        <Stat icon={<ActivityIcon className="h-4 w-4" />} label="Distance">
          {formatDistance(activity.distance_m)}
        </Stat>
        <Stat icon={<Timer className="h-4 w-4" />} label="Duration">
          {formatDuration(activity.duration_s)}
        </Stat>
        <Stat icon={<Gauge className="h-4 w-4" />} label="Avg pace">
          {formatPace(activity.avg_pace_s_per_km)}
        </Stat>
        <Stat icon={<HeartPulse className="h-4 w-4" />} label="Avg HR">
          {activity.avg_hr ? `${Math.round(activity.avg_hr)} bpm` : "—"}
        </Stat>
      </dl>
    </div>
  );
}

function Stat({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-400">
        {icon}
        {label}
      </dt>
      <dd className="mt-0.5 text-sm font-semibold text-slate-800">{children}</dd>
    </div>
  );
}

export function MyBoard() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["garmin-status"],
    queryFn: garminApi.status,
  });

  const connected = !!status?.connected;

  const { data: latest, isLoading: latestLoading } = useQuery({
    queryKey: ["garmin-activities", "latest"],
    queryFn: () => garminApi.activities({ limit: 1 }),
    enabled: connected,
  });

  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const [start, setStart] = useState(isoDaysAgo(30));
  const [end, setEnd] = useState(todayIso());
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [results, setResults] = useState<ActivitySummary[] | null>(null);
  const [fetchedCount, setFetchedCount] = useState<number | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);

  async function syncNow() {
    setSyncing(true);
    setSyncMessage(null);
    setSyncError(null);
    try {
      const res = await garminApi.sync();
      setSyncMessage(`Synced ${res.activities_synced} activities.`);
      await qc.invalidateQueries({ queryKey: ["garmin-status"] });
      await qc.invalidateQueries({ queryKey: ["garmin-activities"] });
    } catch (err) {
      setSyncError(apiErrorMessage(err));
    } finally {
      setSyncing(false);
    }
  }

  async function extract() {
    if (fetching) return;
    setFetching(true);
    setFetchError(null);
    setFetchedCount(null);
    try {
      const res = await garminApi.fetchActivities(start, end);
      setResults(res.activities);
      setFetchedCount(res.fetched);
      await qc.invalidateQueries({ queryKey: ["garmin-activities"] });
    } catch (err) {
      setFetchError(apiErrorMessage(err));
    } finally {
      setFetching(false);
    }
  }

  if (statusLoading) return <PageLoader />;

  if (!connected) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">My Board</h1>
          <p className="text-sm text-slate-500">
            Your latest activities, straight from your device.
          </p>
        </div>

        <div className="card flex flex-col items-center justify-center gap-3 p-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
            <Watch className="h-6 w-6" />
          </div>
          <h3 className="font-semibold text-slate-800">No device connected</h3>
          <p className="max-w-sm text-sm text-slate-500">
            Connect your Garmin account to see your latest activity and pull workouts by date.
          </p>
          <button className="btn-primary" onClick={() => navigate("/connect")}>
            <Watch className="h-4 w-4" /> Connect Garmin
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">My Board</h1>
          <p className="text-sm text-slate-500">
            Connected as {status?.garmin_email}
            {status?.last_sync_at ? ` · last sync ${formatDate(status.last_sync_at)}` : ""}
          </p>
        </div>
        <button className="btn-secondary" onClick={() => void syncNow()} disabled={syncing}>
          {syncing ? <Spinner /> : <RefreshCw className="h-4 w-4" />} Sync now
        </button>
      </div>

      {syncMessage && <Banner kind="success">{syncMessage}</Banner>}
      {syncError && <Banner kind="error">{syncError}</Banner>}
      {status?.last_sync_error && <Banner kind="warning">{status.last_sync_error}</Banner>}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-800">Last activity</h2>
        {latestLoading ? (
          <div className="card p-5">
            <Spinner />
          </div>
        ) : latest && latest.length > 0 ? (
          <ActivityCard activity={latest[0]} highlight onSelect={setSelectedId} />
        ) : (
          <div className="card p-6 text-center text-sm text-slate-500">
            No activities synced yet. Click <span className="font-medium">Sync now</span> to pull
            your latest workout.
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-800">Find activities</h2>
        <div className="card space-y-4 p-6">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="label" htmlFor="g-start">
                From
              </label>
              <input
                id="g-start"
                type="date"
                className="input"
                value={start}
                max={end}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="g-end">
                To
              </label>
              <input
                id="g-end"
                type="date"
                className="input"
                value={end}
                min={start}
                max={todayIso()}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
            <button
              className="btn-primary"
              onClick={() => void extract()}
              disabled={fetching || !start || !end}
            >
              {fetching ? <Spinner /> : <CalendarSearch className="h-4 w-4" />} Extract
            </button>
          </div>

          {fetchError && <Banner kind="error">{fetchError}</Banner>}

          {results !== null && (
            <div className="space-y-3">
              <p className="text-sm text-slate-500">
                {results.length === 0
                  ? "No activities found in this range."
                  : `${results.length} ${results.length === 1 ? "activity" : "activities"} in range`}
                {fetchedCount !== null && fetchedCount > 0 && (
                  <span className="text-slate-400"> · {fetchedCount} newly pulled</span>
                )}
              </p>
              {results.map((a) => (
                <ActivityCard key={a.id} activity={a} onSelect={setSelectedId} />
              ))}
            </div>
          )}
        </div>
      </section>

      <ActivityDetailModal
        activityId={selectedId}
        open={selectedId !== null}
        onOpenChange={(o) => {
          if (!o) setSelectedId(null);
        }}
      />
    </div>
  );
}
