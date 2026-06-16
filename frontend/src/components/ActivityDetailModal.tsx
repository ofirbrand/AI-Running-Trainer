import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { Activity as ActivityIcon, X } from "lucide-react";
import type { ReactNode } from "react";
import { garminApi } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import {
  formatDate,
  formatDateTime,
  formatDistance,
  formatDuration,
  formatPace,
  titleCase,
} from "../lib/format";
import { Badge, Banner, Spinner } from "./ui";

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold text-slate-800">{children}</dd>
    </div>
  );
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

interface RawField {
  key: string;
  label: string;
  fmt: (v: unknown) => string | null;
}

const intWith = (unit: string) => (v: unknown) => {
  const n = asNumber(v);
  return n === null ? null : `${Math.round(n)}${unit}`;
};

const fixedWith = (unit: string, digits = 1) => (v: unknown) => {
  const n = asNumber(v);
  return n === null ? null : `${n.toFixed(digits)}${unit}`;
};

const RAW_FIELDS: RawField[] = [
  { key: "elevationGain", label: "Elevation gain", fmt: intWith(" m") },
  { key: "elevationLoss", label: "Elevation loss", fmt: intWith(" m") },
  {
    key: "averageRunningCadenceInStepsPerMinute",
    label: "Avg cadence",
    fmt: intWith(" spm"),
  },
  {
    key: "maxRunningCadenceInStepsPerMinute",
    label: "Max cadence",
    fmt: intWith(" spm"),
  },
  { key: "averageSpeed", label: "Avg speed", fmt: fixedWith(" m/s", 2) },
  { key: "maxSpeed", label: "Max speed", fmt: fixedWith(" m/s", 2) },
  { key: "avgPower", label: "Avg power", fmt: intWith(" W") },
  { key: "maxPower", label: "Max power", fmt: intWith(" W") },
  { key: "normPower", label: "Normalized power", fmt: intWith(" W") },
  { key: "aerobicTrainingEffect", label: "Aerobic TE", fmt: fixedWith("", 1) },
  { key: "anaerobicTrainingEffect", label: "Anaerobic TE", fmt: fixedWith("", 1) },
  { key: "vO2MaxValue", label: "VO2 max", fmt: fixedWith("", 1) },
  { key: "minTemperature", label: "Min temp", fmt: intWith("\u00b0") },
  { key: "maxTemperature", label: "Max temp", fmt: intWith("\u00b0") },
  { key: "steps", label: "Steps", fmt: intWith("") },
  {
    key: "locationName",
    label: "Location",
    fmt: (v) => (typeof v === "string" && v.trim() ? v : null),
  },
];

export function ActivityDetailModal({
  activityId,
  open,
  onOpenChange,
}: {
  activityId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const {
    data: detail,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["garmin-activity", activityId],
    queryFn: () => garminApi.activity(activityId as number),
    enabled: open && activityId != null,
  });

  const raw = (detail?.raw ?? {}) as Record<string, unknown>;
  const rawStats = RAW_FIELDS.map((f) => ({ label: f.label, value: f.fmt(raw[f.key]) })).filter(
    (s) => s.value !== null,
  );

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[92vw] max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl bg-white shadow-xl">
          <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
            <Dialog.Title className="flex items-center gap-2 font-semibold text-slate-900">
              <ActivityIcon className="h-5 w-5 text-brand-600" />
              {detail
                ? detail.name || titleCase(detail.activity_type) || "Activity"
                : "Activity"}
            </Dialog.Title>
            <Dialog.Close className="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
            {isLoading && (
              <div className="flex justify-center py-8">
                <Spinner className="h-6 w-6" />
              </div>
            )}
            {isError && <Banner kind="error">{apiErrorMessage(error)}</Banner>}

            {detail && (
              <>
                <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
                  {detail.activity_type && (
                    <Badge color="green">{titleCase(detail.activity_type)}</Badge>
                  )}
                  <span>{formatDate(detail.activity_date)}</span>
                </div>

                <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
                  <Stat label="Start time">{formatDateTime(detail.start_time)}</Stat>
                  <Stat label="Distance">{formatDistance(detail.distance_m)}</Stat>
                  <Stat label="Duration">{formatDuration(detail.duration_s)}</Stat>
                  <Stat label="Avg pace">{formatPace(detail.avg_pace_s_per_km)}</Stat>
                  <Stat label="Avg HR">
                    {detail.avg_hr ? `${Math.round(detail.avg_hr)} bpm` : "—"}
                  </Stat>
                  <Stat label="Max HR">
                    {detail.max_hr ? `${Math.round(detail.max_hr)} bpm` : "—"}
                  </Stat>
                  <Stat label="Calories">
                    {detail.calories ? `${Math.round(detail.calories)} kcal` : "—"}
                  </Stat>
                  {rawStats.map((s) => (
                    <Stat key={s.label} label={s.label}>
                      {s.value}
                    </Stat>
                  ))}
                </dl>

                <details className="rounded-lg border border-slate-200">
                  <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-slate-600">
                    Raw data
                  </summary>
                  <pre className="max-h-80 overflow-auto px-4 pb-3 text-xs text-slate-600">
                    {JSON.stringify(detail.raw ?? {}, null, 2)}
                  </pre>
                </details>
              </>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
