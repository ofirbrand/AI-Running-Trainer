import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { garminApi, plansApi, profileApi } from "../api/endpoints";
import type { PrefillResponse } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { Banner, Field, PageLoader, Spinner } from "../components/ui";
import { AIProcessingModal, useAIProcessing } from "../components/AIProcessingStream";
import { InfoTip } from "../components/InfoTip";
import { EMPTY_PROFILE, ProfileForm } from "../components/ProfileForm";
import { formatDate } from "../lib/format";
import type { PlanInputs, Profile } from "../api/types";

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const DISTANCES = ["5K", "10K", "Half Marathon", "Marathon", "Other"];

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const EMPTY_INPUTS: PlanInputs = {
  title: "",
  distance_label: "10K",
  target_date: "",
  goal_type: "finish",
  goal_value: "",
  is_race: false,
  current_weekly_volume: "",
  training_frequency_days: null,
  experience_level: "",
  days_available: [],
  time_per_session: "",
  time_per_session_by_day: {},
  preferred_long_run_day: "Sunday",
  strength_work: "",
  other_sports: "",
  mobility_prehab: "",
  longest_run_last_month_km: null,
  vo2max: null,
  resting_hr: null,
  max_hr: null,
  threshold_hr: null,
  training_load: "",
  include_activity_history: false,
  activity_history_start: null,
  activity_history_end: null,
  extra_notes: "",
};

function MetricField({
  label,
  term,
  field,
  prefill,
  value,
  onChange,
  unit,
  placeholder,
}: {
  label: string;
  term?: string;
  field: string;
  prefill: PrefillResponse["prefill"];
  value: number | null | undefined;
  onChange: (v: number | null) => void;
  unit?: string;
  placeholder?: string;
}) {
  const meta = prefill[field];
  return (
    <Field label={label} info={term ? <InfoTip term={term} /> : undefined}>
      <div className="relative">
        <input
          type="number"
          step="any"
          className="input"
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
          placeholder={placeholder}
        />
        {unit && (
          <span className="pointer-events-none absolute right-3 top-2 text-xs text-slate-400">
            {unit}
          </span>
        )}
      </div>
      {meta?.measured_at && (
        <p className="mt-1 text-xs text-slate-400">
          Last updated {formatDate(meta.measured_at)}
          {meta.source ? ` from ${meta.source}` : ""}
        </p>
      )}
    </Field>
  );
}

export function CreatePlanPage() {
  const navigate = useNavigate();
  const { data: prefill, isLoading } = useQuery({
    queryKey: ["prefill"],
    queryFn: plansApi.prefill,
  });
  const { data: garmin } = useQuery({
    queryKey: ["garmin-status"],
    queryFn: garminApi.status,
  });
  const garminConnected = !!garmin?.connected;

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [profile, setProfile] = useState<Profile>({ ...EMPTY_PROFILE });
  const [inputs, setInputs] = useState<PlanInputs>({ ...EMPTY_INPUTS });
  const [varyByDay, setVaryByDay] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ai = useAIProcessing();

  useEffect(() => {
    if (!prefill) return;
    setProfile({ ...EMPTY_PROFILE, ...prefill.profile, personal_records: prefill.profile.personal_records ?? [] });
    const p = prefill.prefill;
    const num = (k: string) => {
      const v = p[k]?.value;
      return typeof v === "number" ? v : v ? Number(v) : null;
    };
    setInputs((cur) => ({
      ...cur,
      vo2max: num("vo2max"),
      resting_hr: num("resting_hr"),
      max_hr: num("max_hr"),
      threshold_hr: num("threshold_hr"),
      longest_run_last_month_km: num("longest_run_last_month_km"),
      training_load: (p.training_load?.value as string) ?? "",
      current_weekly_volume:
        p.current_weekly_volume?.value != null
          ? `${p.current_weekly_volume.value} ${p.current_weekly_volume.unit ?? ""}`.trim()
          : cur.current_weekly_volume,
      training_frequency_days: num("training_frequency_days"),
      experience_level: (p.experience_level?.value as string) ?? cur.experience_level,
    }));
  }, [prefill]);

  function set<K extends keyof PlanInputs>(key: K, v: PlanInputs[K]) {
    setInputs((cur) => ({ ...cur, [key]: v }));
  }

  function toggleDay(day: string) {
    const has = inputs.days_available.includes(day);
    set("days_available", has ? inputs.days_available.filter((d) => d !== day) : [...inputs.days_available, day]);
  }

  function toggleActivityHistory(include: boolean) {
    setInputs((cur) => ({
      ...cur,
      include_activity_history: include,
      activity_history_start: include ? cur.activity_history_start ?? isoDaysAgo(90) : cur.activity_history_start,
      activity_history_end: include ? cur.activity_history_end ?? todayIso() : cur.activity_history_end,
    }));
  }

  async function continueFromProfile() {
    setBusy(true);
    setError(null);
    try {
      await profileApi.update(profile);
      setStep(2);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function validateStep2(): string | null {
    if (!inputs.distance_label) return "Choose a distance.";
    if (!inputs.target_date) return "Choose a target date.";
    if (new Date(inputs.target_date) <= new Date()) return "Target date must be in the future.";
    if (inputs.days_available.length === 0) return "Select at least one available training day.";
    return null;
  }

  async function generate() {
    const includeHistory = inputs.include_activity_history && garminConnected;
    if (includeHistory) {
      if (!inputs.activity_history_start || !inputs.activity_history_end) {
        setError("Choose a date range for your activity history.");
        return;
      }
      if (inputs.activity_history_start > inputs.activity_history_end) {
        setError("Activity history start date must be on or before the end date.");
        return;
      }
    }
    setBusy(true);
    setError(null);
    try {
      const payload: PlanInputs = {
        ...inputs,
        time_per_session_by_day: varyByDay ? inputs.time_per_session_by_day : {},
        include_activity_history: includeHistory,
        activity_history_start: includeHistory ? inputs.activity_history_start : null,
        activity_history_end: includeHistory ? inputs.activity_history_end : null,
      };
      const done = await ai.run("/plans/stream", payload);
      navigate(`/plans/${done.plan_id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : apiErrorMessage(err, "Could not generate the plan.");
      setError(message);
      setBusy(false);
    }
  }

  if (isLoading) return <PageLoader />;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">New training plan</h1>
        <p className="text-sm text-slate-500">Step {step} of 3</p>
      </div>

      <div className="flex gap-2">
        {[1, 2, 3].map((s) => (
          <div
            key={s}
            className={`h-1.5 flex-1 rounded-full ${s <= step ? "bg-brand-500" : "bg-slate-200"}`}
          />
        ))}
      </div>

      {error && <Banner kind="error">{error}</Banner>}

      {step === 1 && (
        <div className="card p-6">
          <h2 className="mb-1 text-lg font-semibold text-slate-800">Confirm your profile</h2>
          <p className="mb-4 text-sm text-slate-500">
            Review and update your details so the plan reflects your current state.
          </p>
          <ProfileForm value={profile} onChange={setProfile} />
          <div className="mt-6 flex justify-end">
            <button className="btn-primary" onClick={() => void continueFromProfile()} disabled={busy}>
              {busy && <Spinner />} Continue
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="card space-y-5 p-6">
          <h2 className="text-lg font-semibold text-slate-800">Plan details</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Distance">
              <select
                className="input"
                value={inputs.distance_label}
                onChange={(e) => set("distance_label", e.target.value)}
              >
                {DISTANCES.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </Field>
            <Field label="Target date">
              <input
                type="date"
                className="input"
                value={inputs.target_date}
                onChange={(e) => set("target_date", e.target.value)}
              />
            </Field>
            <Field label="Goal type">
              <select
                className="input"
                value={inputs.goal_type}
                onChange={(e) => set("goal_type", e.target.value as PlanInputs["goal_type"])}
              >
                <option value="finish">Just finish</option>
                <option value="time">Goal time</option>
                <option value="pace">Goal pace</option>
              </select>
            </Field>
            <Field
              label="Goal value"
              info={<InfoTip term="goal_pace" />}
            >
              <input
                className="input"
                placeholder="e.g. 45:00 or 4:30/km"
                value={inputs.goal_value ?? ""}
                onChange={(e) => set("goal_value", e.target.value)}
                disabled={inputs.goal_type === "finish"}
              />
            </Field>
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={inputs.is_race}
              onChange={(e) => set("is_race", e.target.checked)}
            />
            This is a race
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Current weekly volume" info={<InfoTip term="weekly_volume" />}>
              <input
                className="input"
                placeholder="e.g. 40 km or 5 hours"
                value={inputs.current_weekly_volume ?? ""}
                onChange={(e) => set("current_weekly_volume", e.target.value)}
              />
            </Field>
            <Field label="Current runs per week" info={<InfoTip term="training_frequency" />}>
              <input
                type="number"
                className="input"
                value={inputs.training_frequency_days ?? ""}
                onChange={(e) =>
                  set("training_frequency_days", e.target.value ? Number(e.target.value) : null)
                }
              />
            </Field>
            <Field label="Experience level">
              <input
                className="input"
                placeholder="beginner / 3 years / advanced"
                value={inputs.experience_level ?? ""}
                onChange={(e) => set("experience_level", e.target.value)}
              />
            </Field>
            <Field label="Preferred long-run day" info={<InfoTip term="long_run" />}>
              <select
                className="input"
                value={inputs.preferred_long_run_day ?? ""}
                onChange={(e) => set("preferred_long_run_day", e.target.value)}
              >
                {WEEKDAYS.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Days available to train">
            <div className="flex flex-wrap gap-2">
              {WEEKDAYS.map((d) => {
                const active = inputs.days_available.includes(d);
                return (
                  <button
                    key={d}
                    type="button"
                    onClick={() => toggleDay(d)}
                    className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                      active
                        ? "border-brand-500 bg-brand-50 text-brand-700"
                        : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {d.slice(0, 3)}
                  </button>
                );
              })}
            </div>
          </Field>

          <Field label="Typical time per session">
            <input
              className="input"
              placeholder="e.g. 60 minutes"
              value={inputs.time_per_session ?? ""}
              onChange={(e) => set("time_per_session", e.target.value)}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={varyByDay} onChange={(e) => setVaryByDay(e.target.checked)} />
            My available time varies by day
          </label>
          {varyByDay && (
            <div className="grid gap-2 sm:grid-cols-2">
              {inputs.days_available.map((d) => (
                <Field key={d} label={d}>
                  <input
                    className="input"
                    placeholder="e.g. 45 minutes"
                    value={inputs.time_per_session_by_day[d] ?? ""}
                    onChange={(e) =>
                      set("time_per_session_by_day", {
                        ...inputs.time_per_session_by_day,
                        [d]: e.target.value,
                      })
                    }
                  />
                </Field>
              ))}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Strength work & gym access" info={<InfoTip term="strength" />}>
              <input
                className="input"
                placeholder="e.g. willing, 2x/week, has gym"
                value={inputs.strength_work ?? ""}
                onChange={(e) => set("strength_work", e.target.value)}
              />
            </Field>
            <Field label="Other sports / activities">
              <input
                className="input"
                placeholder="e.g. cycling Tue, football Fri"
                value={inputs.other_sports ?? ""}
                onChange={(e) => set("other_sports", e.target.value)}
              />
            </Field>
          </div>
          <Field label="Mobility / prehab habits" info={<InfoTip term="mobility" />}>
            <input
              className="input"
              placeholder="e.g. dynamic warm-up, hip mobility 2x/week"
              value={inputs.mobility_prehab ?? ""}
              onChange={(e) => set("mobility_prehab", e.target.value)}
            />
          </Field>

          <div className="flex justify-between">
            <button className="btn-secondary" onClick={() => setStep(1)}>
              Back
            </button>
            <button
              className="btn-primary"
              onClick={() => {
                const err = validateStep2();
                if (err) {
                  setError(err);
                  return;
                }
                setError(null);
                setStep(3);
              }}
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="card space-y-5 p-6">
          <h2 className="text-lg font-semibold text-slate-800">Fitness metrics</h2>
          <p className="text-sm text-slate-500">
            Pulled from Garmin where available — confirm or override. Anything blank you can fill in
            manually.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <MetricField label="VO2 max" term="vo2max" field="vo2max" prefill={prefill?.prefill ?? {}} value={inputs.vo2max} onChange={(v) => set("vo2max", v)} />
            <MetricField label="Resting HR" term="resting_hr" field="resting_hr" prefill={prefill?.prefill ?? {}} value={inputs.resting_hr} onChange={(v) => set("resting_hr", v)} unit="bpm" />
            <MetricField label="Max HR" term="max_hr" field="max_hr" prefill={prefill?.prefill ?? {}} value={inputs.max_hr} onChange={(v) => set("max_hr", v)} unit="bpm" />
            <MetricField label="Threshold HR" term="threshold_hr" field="threshold_hr" prefill={prefill?.prefill ?? {}} value={inputs.threshold_hr} onChange={(v) => set("threshold_hr", v)} unit="bpm" />
            <MetricField label="Longest run (last month)" term="longest_run" field="longest_run_last_month_km" prefill={prefill?.prefill ?? {}} value={inputs.longest_run_last_month_km} onChange={(v) => set("longest_run_last_month_km", v)} unit="km" />
            <Field label="Training load / trend" info={<InfoTip term="training_load" />}>
              <input
                className="input"
                value={inputs.training_load ?? ""}
                onChange={(e) => set("training_load", e.target.value)}
                placeholder="e.g. productive, ~700"
              />
            </Field>
          </div>

          <Field label="Anything else for the coach?">
            <textarea
              className="input min-h-[70px]"
              value={inputs.extra_notes ?? ""}
              onChange={(e) => set("extra_notes", e.target.value)}
              placeholder="Optional context, constraints, or preferences."
            />
          </Field>

          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
            <h3 className="text-sm font-semibold text-slate-800">Garmin activity history</h3>
            {garminConnected ? (
              <>
                <label className="mt-2 flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={inputs.include_activity_history}
                    onChange={(e) => toggleActivityHistory(e.target.checked)}
                  />
                  Include my Garmin activity history when building the plan
                </label>
                {inputs.include_activity_history && (
                  <>
                    <p className="mt-3 text-xs text-slate-500">
                      The coach will pull your activities from this date range and factor them into
                      your plan.
                    </p>
                    <div className="mt-2 grid gap-4 sm:grid-cols-2">
                      <Field label="From">
                        <input
                          type="date"
                          className="input"
                          value={inputs.activity_history_start ?? ""}
                          max={inputs.activity_history_end ?? todayIso()}
                          onChange={(e) => set("activity_history_start", e.target.value || null)}
                        />
                      </Field>
                      <Field label="To">
                        <input
                          type="date"
                          className="input"
                          value={inputs.activity_history_end ?? ""}
                          min={inputs.activity_history_start ?? undefined}
                          max={todayIso()}
                          onChange={(e) => set("activity_history_end", e.target.value || null)}
                        />
                      </Field>
                    </div>
                  </>
                )}
              </>
            ) : (
              <p className="mt-2 text-sm text-slate-500">
                Connect your Garmin to include your activity history.{" "}
                <button
                  type="button"
                  className="font-medium text-brand-600 hover:underline"
                  onClick={() => navigate("/connect")}
                >
                  Connect Garmin
                </button>
              </p>
            )}
          </div>

          <div className="flex justify-between">
            <button className="btn-secondary" onClick={() => setStep(2)} disabled={busy}>
              Back
            </button>
            <button className="btn-primary" onClick={() => void generate()} disabled={busy}>
              {busy ? <Spinner /> : <Sparkles className="h-4 w-4" />}
              {busy ? "Generating plan…" : "Generate plan"}
            </button>
          </div>
          {busy && (
            <p className="text-center text-sm text-slate-400">
              The coach is designing your plan — watch it work below.
            </p>
          )}
        </div>
      )}

      <AIProcessingModal trace={ai.trace} open={ai.open} onOpenChange={ai.setOpen} />
    </div>
  );
}
