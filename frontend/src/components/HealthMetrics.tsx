/**
 * Renders the two live Garmin metric groups on "My Board":
 *   - Daily Health & Activity   (9 garminconnect methods)
 *   - Advanced Health Metrics   (12 garminconnect methods)
 *
 * Garmin's payloads are deeply nested and vary by device/firmware, so each
 * metric has a defensive `summarize()` that pulls the high-value headline
 * fields with optional chaining. Whatever can't be parsed is never lost: every
 * card also exposes the full raw payload in a collapsible "Raw data" section.
 */
import { useMemo } from "react";
import {
  Activity,
  Brain,
  Cake,
  Droplets,
  FlaskConical,
  Footprints,
  Gauge,
  Heart,
  HeartPulse,
  Moon,
  Mountain,
  Scale,
  Sparkles,
  Sunrise,
  Timer,
  TrendingUp,
  Waves,
  Wind,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { formatDistance, formatPace, titleCase } from "../lib/format";

type Stat = { label: string; value: string };

interface MetricDef {
  key: string;
  title: string;
  icon: LucideIcon;
  summarize: (raw: any) => Stat[];
}

// --- small, defensive helpers --------------------------------------------- //

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const asObj = (v: unknown): any => (v && typeof v === "object" ? v : {});
const asArr = (v: unknown): any[] => (Array.isArray(v) ? v : []);
const r = (v: unknown): number | undefined => (isNum(v) ? Math.round(v) : undefined);

function add(
  stats: Stat[],
  label: string,
  value: string | number | null | undefined,
  suffix = "",
): void {
  if (value === null || value === undefined || value === "") return;
  if (typeof value === "number" && !Number.isFinite(value)) return;
  stats.push({ label, value: `${value}${suffix}` });
}

function hoursMinutes(seconds: unknown): string | null {
  if (!isNum(seconds) || seconds <= 0) return null;
  const total = Math.round(seconds / 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function paceFromSpeed(metersPerSecond: unknown): string | null {
  if (!isNum(metersPerSecond) || metersPerSecond <= 0) return null;
  return formatPace(1000 / metersPerSecond);
}

// --- Daily Health & Activity summarizers ---------------------------------- //

// get_stats and get_user_summary share the daily user-summary shape.
function summarizeUserSummary(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  add(s, "Steps", isNum(d.totalSteps) ? d.totalSteps : undefined);
  add(s, "Calories", r(d.totalKilocalories), " kcal");
  if (isNum(d.totalDistanceMeters)) add(s, "Distance", formatDistance(d.totalDistanceMeters));
  add(s, "Resting HR", isNum(d.restingHeartRate) ? d.restingHeartRate : undefined, " bpm");
  add(s, "Avg stress", isNum(d.averageStressLevel) ? d.averageStressLevel : undefined);
  if (isNum(d.bodyBatteryHighestValue) || isNum(d.bodyBatteryLowestValue)) {
    const lo = isNum(d.bodyBatteryLowestValue) ? d.bodyBatteryLowestValue : "—";
    const hi = isNum(d.bodyBatteryHighestValue) ? d.bodyBatteryHighestValue : "—";
    add(s, "Body battery", `${lo}–${hi}`);
  }
  add(s, "Floors", isNum(d.floorsAscended) ? d.floorsAscended : undefined);
  return s;
}

function summarizeStatsAndBody(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  if (isNum(d.weight)) add(s, "Weight", (d.weight / 1000).toFixed(1), " kg"); // grams → kg
  if (isNum(d.bmi)) add(s, "BMI", d.bmi.toFixed(1));
  if (isNum(d.bodyFat)) add(s, "Body fat", d.bodyFat.toFixed(1), "%");
  if (isNum(d.bodyWater)) add(s, "Body water", d.bodyWater.toFixed(1), "%");
  add(s, "Steps", isNum(d.totalSteps) ? d.totalSteps : undefined);
  add(s, "Resting HR", isNum(d.restingHeartRate) ? d.restingHeartRate : undefined, " bpm");
  return s;
}

function summarizeSteps(raw: any): Stat[] {
  const s: Stat[] = [];
  const list = asArr(raw);
  if (list.length === 0) return s;
  const total = list.reduce((sum, it) => sum + (isNum(it?.steps) ? it.steps : 0), 0);
  add(s, "Total steps", total);
  add(s, "Intervals", list.length);
  return s;
}

function summarizeHeartRates(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  add(s, "Resting HR", isNum(d.restingHeartRate) ? d.restingHeartRate : undefined, " bpm");
  add(s, "Min HR", isNum(d.minHeartRate) ? d.minHeartRate : undefined, " bpm");
  add(s, "Max HR", isNum(d.maxHeartRate) ? d.maxHeartRate : undefined, " bpm");
  add(
    s,
    "7-day rest avg",
    isNum(d.lastSevenDaysAvgRestingHeartRate) ? d.lastSevenDaysAvgRestingHeartRate : undefined,
    " bpm",
  );
  if (Array.isArray(d.heartRateValues)) add(s, "Samples", d.heartRateValues.length);
  return s;
}

function summarizeRhrDay(raw: any): Stat[] {
  const s: Stat[] = [];
  const map = asObj(asObj(asObj(raw).allMetrics).metricsMap);
  const series = asArr(map.WELLNESS_RESTING_HEART_RATE);
  const value = series.length ? series[series.length - 1]?.value : undefined;
  add(s, "Resting HR", isNum(value) ? value : undefined, " bpm");
  return s;
}

function summarizeSleep(raw: any): Stat[] {
  const s: Stat[] = [];
  const dto = asObj(asObj(raw).dailySleepDTO);
  const total = hoursMinutes(dto.sleepTimeSeconds);
  if (total) add(s, "Total sleep", total);
  const overall = asObj(asObj(dto.sleepScores).overall).value;
  add(s, "Sleep score", isNum(overall) ? overall : undefined);
  const deep = hoursMinutes(dto.deepSleepSeconds);
  const light = hoursMinutes(dto.lightSleepSeconds);
  const rem = hoursMinutes(dto.remSleepSeconds);
  const awake = hoursMinutes(dto.awakeSleepSeconds);
  if (deep) add(s, "Deep", deep);
  if (light) add(s, "Light", light);
  if (rem) add(s, "REM", rem);
  if (awake) add(s, "Awake", awake);
  return s;
}

function summarizeAllDayStress(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  add(s, "Avg stress", isNum(d.avgStressLevel) ? d.avgStressLevel : undefined);
  add(s, "Max stress", isNum(d.maxStressLevel) ? d.maxStressLevel : undefined);
  if (Array.isArray(d.stressValuesArray)) add(s, "Stress samples", d.stressValuesArray.length);
  if (Array.isArray(d.bodyBatteryValuesArray))
    add(s, "Body battery samples", d.bodyBatteryValuesArray.length);
  return s;
}

// --- Advanced Health Metrics summarizers ---------------------------------- //

// Shared by get_training_readiness (list) and get_morning_training_readiness (dict).
function summarizeReadiness(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = Array.isArray(raw) ? asObj(raw[0]) : asObj(raw);
  add(s, "Score", isNum(d.score) ? d.score : undefined);
  if (d.level) add(s, "Level", titleCase(String(d.level)));
  if (d.feedbackShort) add(s, "Feedback", titleCase(String(d.feedbackShort)));
  add(s, "Sleep score", isNum(d.sleepScore) ? d.sleepScore : undefined);
  if (isNum(d.recoveryTime)) add(s, "Recovery", `${d.recoveryTime} min`);
  return s;
}

function summarizeTrainingStatus(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  const vo2 = asObj(asObj(d.mostRecentVO2Max).generic).vo2MaxValue;
  add(s, "VO₂ max", isNum(vo2) ? vo2 : undefined);
  // Training load and the status phrase are both keyed by device id.
  const loadMap = asObj(asObj(d.mostRecentTrainingLoadBalance).metricsTrainingLoadBalanceDTOMap);
  for (const entry of Object.values(loadMap)) {
    const load = asObj(entry).monthlyLoad;
    if (isNum(load)) {
      add(s, "Monthly load", Math.round(load));
      break;
    }
  }
  const statusMap = asObj(asObj(d.mostRecentTrainingStatus).latestTrainingStatusData);
  for (const entry of Object.values(statusMap)) {
    const phrase = asObj(entry).trainingStatusFeedbackPhrase ?? asObj(entry).trainingStatus;
    if (phrase) {
      add(s, "Status", titleCase(String(phrase)));
      break;
    }
  }
  return s;
}

function summarizeRespiration(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  add(s, "Avg waking", isNum(d.avgWakingRespirationValue) ? d.avgWakingRespirationValue : undefined, " brpm");
  add(s, "Avg sleep", isNum(d.avgSleepRespirationValue) ? d.avgSleepRespirationValue : undefined, " brpm");
  add(s, "Lowest", isNum(d.lowestRespirationValue) ? d.lowestRespirationValue : undefined, " brpm");
  add(s, "Highest", isNum(d.highestRespirationValue) ? d.highestRespirationValue : undefined, " brpm");
  return s;
}

function summarizeSpo2(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  add(s, "Average", isNum(d.averageSpO2) ? d.averageSpO2 : undefined, "%");
  add(s, "Lowest", isNum(d.lowestSpO2) ? d.lowestSpO2 : undefined, "%");
  add(s, "Latest", isNum(d.latestSpO2) ? d.latestSpO2 : undefined, "%");
  return s;
}

function summarizeMaxMetrics(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = Array.isArray(raw) ? asObj(raw[0]) : asObj(raw);
  const generic = asObj(d.generic);
  add(s, "VO₂ max", isNum(generic.vo2MaxValue) ? generic.vo2MaxValue : undefined);
  add(s, "Fitness age", isNum(generic.fitnessAge) ? generic.fitnessAge.toFixed(2) : undefined);
  const cycling = asObj(d.cycling);
  add(s, "VO₂ max (cycling)", isNum(cycling.vo2MaxValue) ? cycling.vo2MaxValue : undefined);
  return s;
}

function summarizeHrv(raw: any): Stat[] {
  const s: Stat[] = [];
  const sum = asObj(asObj(raw).hrvSummary);
  add(s, "Last night avg", isNum(sum.lastNightAvg) ? sum.lastNightAvg : undefined, " ms");
  add(s, "5-min high", isNum(sum.lastNight5MinHigh) ? sum.lastNight5MinHigh : undefined, " ms");
  add(s, "Weekly avg", isNum(sum.weeklyAvg) ? sum.weeklyAvg : undefined, " ms");
  if (sum.status) add(s, "Status", titleCase(String(sum.status)));
  return s;
}

function summarizeFitnessAge(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  add(s, "Fitness age", isNum(d.fitnessAge) ? d.fitnessAge.toFixed(2) : undefined);
  add(s, "Chronological age", isNum(d.chronologicalAge) ? d.chronologicalAge : undefined);
  add(s, "Achievable", isNum(d.achievableFitnessAge) ? d.achievableFitnessAge.toFixed(2) : undefined);
  return s;
}

function summarizeStress(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  add(s, "Avg stress", isNum(d.avgStressLevel) ? d.avgStressLevel : undefined);
  add(s, "Max stress", isNum(d.maxStressLevel) ? d.maxStressLevel : undefined);
  if (Array.isArray(d.stressValuesArray)) add(s, "Samples", d.stressValuesArray.length);
  return s;
}

function summarizeLactateThreshold(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  const shr = asObj(d.speed_and_heart_rate);
  add(s, "Threshold HR", isNum(shr.heartRate) ? shr.heartRate : undefined, " bpm");
  const pace = paceFromSpeed(shr.speed);
  if (pace) add(s, "Threshold pace", pace);
  const power = asObj(d.power);
  add(
    s,
    "Threshold power",
    isNum(power.functionalThresholdPower) ? power.functionalThresholdPower : undefined,
    " W",
  );
  return s;
}

function summarizeIntensityMinutes(raw: any): Stat[] {
  const s: Stat[] = [];
  const d = asObj(raw);
  const moderate = d.moderateMinutes ?? d.moderateValue;
  const vigorous = d.vigorousMinutes ?? d.vigorousValue;
  add(s, "Moderate", isNum(moderate) ? moderate : undefined, " min");
  add(s, "Vigorous", isNum(vigorous) ? vigorous : undefined, " min");
  add(s, "Weekly goal", isNum(d.weeklyGoal) ? d.weeklyGoal : undefined);
  return s;
}

function summarizeRunningTolerance(raw: any): Stat[] {
  const s: Stat[] = [];
  const list = asArr(raw);
  if (list.length === 0) return s;
  const last = asObj(list[list.length - 1]);
  add(s, "Data points", list.length);
  if (last.calendarDate) add(s, "Latest", String(last.calendarDate));
  const tolerance = last.runningTolerance ?? last.acuteLoad ?? last.tolerance;
  add(s, "Tolerance", isNum(tolerance) ? Math.round(tolerance) : undefined);
  return s;
}

// --- Metric definitions (display order matches the backend method groups) -- //

export const DAILY_HEALTH_DEFS: MetricDef[] = [
  { key: "stats", title: "Daily stats", icon: Activity, summarize: summarizeUserSummary },
  { key: "user_summary", title: "User summary", icon: Gauge, summarize: summarizeUserSummary },
  {
    key: "stats_and_body",
    title: "Stats & body composition",
    icon: Scale,
    summarize: summarizeStatsAndBody,
  },
  { key: "steps", title: "Steps", icon: Footprints, summarize: summarizeSteps },
  { key: "heart_rates", title: "Heart rate", icon: HeartPulse, summarize: summarizeHeartRates },
  {
    key: "resting_heart_rate",
    title: "Resting heart rate",
    icon: Heart,
    summarize: summarizeRhrDay,
  },
  { key: "sleep", title: "Sleep", icon: Moon, summarize: summarizeSleep },
  { key: "all_day_stress", title: "All-day stress", icon: Brain, summarize: summarizeAllDayStress },
  { key: "lifestyle_logging", title: "Lifestyle logging", icon: Sparkles, summarize: () => [] },
];

export const ADVANCED_HEALTH_DEFS: MetricDef[] = [
  {
    key: "training_readiness",
    title: "Training readiness",
    icon: Zap,
    summarize: summarizeReadiness,
  },
  {
    key: "morning_training_readiness",
    title: "Morning readiness",
    icon: Sunrise,
    summarize: summarizeReadiness,
  },
  {
    key: "training_status",
    title: "Training status",
    icon: TrendingUp,
    summarize: summarizeTrainingStatus,
  },
  { key: "respiration", title: "Respiration", icon: Wind, summarize: summarizeRespiration },
  { key: "spo2", title: "Pulse Ox (SpO₂)", icon: Droplets, summarize: summarizeSpo2 },
  { key: "max_metrics", title: "Max metrics (VO₂ max)", icon: Gauge, summarize: summarizeMaxMetrics },
  { key: "hrv", title: "Heart rate variability", icon: Waves, summarize: summarizeHrv },
  { key: "fitness_age", title: "Fitness age", icon: Cake, summarize: summarizeFitnessAge },
  { key: "stress", title: "Stress", icon: Brain, summarize: summarizeStress },
  {
    key: "lactate_threshold",
    title: "Lactate threshold",
    icon: FlaskConical,
    summarize: summarizeLactateThreshold,
  },
  {
    key: "intensity_minutes",
    title: "Intensity minutes",
    icon: Timer,
    summarize: summarizeIntensityMinutes,
  },
  {
    key: "running_tolerance",
    title: "Running tolerance",
    icon: Mountain,
    summarize: summarizeRunningTolerance,
  },
];

// --- Rendering ------------------------------------------------------------- //

function isEmpty(raw: unknown): boolean {
  if (raw === null || raw === undefined) return true;
  if (Array.isArray(raw)) return raw.length === 0;
  if (typeof raw === "object") return Object.keys(raw as object).length === 0;
  return false;
}

function RawDetails({ raw }: { raw: unknown }) {
  const text = useMemo(() => {
    try {
      const json = JSON.stringify(raw, null, 2);
      return json.length > 20000 ? `${json.slice(0, 20000)}\n… (truncated)` : json;
    } catch {
      return String(raw);
    }
  }, [raw]);
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-xs font-medium text-slate-400 hover:text-slate-600">
        Raw data
      </summary>
      <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
        {text}
      </pre>
    </details>
  );
}

function MetricCard({ def, raw }: { def: MetricDef; raw: unknown }) {
  const empty = isEmpty(raw);
  const stats = empty ? [] : def.summarize(raw);
  const Icon = def.icon;
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
          <Icon className="h-4 w-4" />
        </span>
        <h3 className="font-semibold text-slate-900">{def.title}</h3>
      </div>
      {empty ? (
        <p className="mt-3 text-sm text-slate-400">No data for this date.</p>
      ) : stats.length > 0 ? (
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3">
          {stats.map((s) => (
            <div key={s.label}>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">
                {s.label}
              </dt>
              <dd className="mt-0.5 text-sm font-semibold text-slate-800">{s.value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="mt-3 text-sm text-slate-500">Data available — expand below.</p>
      )}
      {!empty && <RawDetails raw={raw} />}
    </div>
  );
}

export function HealthGrid({
  defs,
  data,
}: {
  defs: MetricDef[];
  data?: Record<string, unknown> | null;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {defs.map((d) => (
        <MetricCard key={d.key} def={d} raw={data?.[d.key]} />
      ))}
    </div>
  );
}
