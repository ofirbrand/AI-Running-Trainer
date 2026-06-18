export interface PersonalRecord {
  distance: string;
  time?: string | null;
  date?: string | null;
}

export interface Profile {
  name?: string | null;
  height_cm?: number | null;
  weight_kg?: number | null;
  gender?: string | null;
  date_of_birth?: string | null;
  personal_records: PersonalRecord[];
  notes?: string | null;
  updated_at?: string | null;
}

export interface GarminStatus {
  connected: boolean;
  garmin_email?: string | null;
  status?: string | null;
  last_sync_at?: string | null;
  last_sync_error?: string | null;
}

export interface SyncResult {
  activities_synced: number;
  days_health_synced: number;
  metrics_updated: number;
  errors: string[];
  last_sync_at?: string | null;
}

/**
 * Live daily-health (9 methods) and advanced-health (12 methods) metric sets.
 * Each value is the raw Garmin payload for that method, keyed by metric name,
 * or null when unavailable for the requested date.
 */
export interface GarminHealth {
  date: string;
  daily: Record<string, unknown>;
  advanced: Record<string, unknown>;
}

export interface Metric {
  key: string;
  value: unknown;
  unit?: string | null;
  source: string;
  measured_at?: string | null;
  updated_at?: string | null;
}

export interface Settings {
  ai_model: string;
  reasoning_effort: string;
}

export interface PlannedWorkout {
  id: number;
  week_no: number;
  weekday: number;
  date: string;
  workout_type: string;
  goal?: string | null;
  how_to?: string | null;
  details?: Record<string, unknown> | null;
}

export interface WorkoutType {
  name: string;
  description: string;
}

export interface PlanVersion {
  id: number;
  plan_id: number;
  version_no: number;
  status: string;
  source: string;
  structure_explanation?: string | null;
  full_explanation?: string | null;
  change_summary?: string | null;
  workout_types?: WorkoutType[] | null;
  start_date?: string | null;
  num_weeks?: number | null;
  created_at: string;
  planned_workouts: PlannedWorkout[];
}

export interface PlanSummary {
  id: number;
  title: string;
  distance_label?: string | null;
  target_date?: string | null;
  goal_type?: string | null;
  goal_value?: string | null;
  is_race: boolean;
  status: string;
  active_version_id?: number | null;
  created_at: string;
}

export interface PlanDetail extends PlanSummary {
  active_version?: PlanVersion | null;
  versions: PlanVersion[];
}

export interface ActivitySummary {
  id: number;
  activity_date: string;
  activity_type?: string | null;
  name?: string | null;
  distance_m?: number | null;
  duration_s?: number | null;
  avg_hr?: number | null;
  avg_pace_s_per_km?: number | null;
}

export interface ActivityFetchResult {
  fetched: number;
  activities: ActivitySummary[];
}

/** One lap / interval split from Garmin's `get_activity_splits` (`lapDTOs`). */
export interface ActivityLap {
  lapIndex?: number | null;
  distance?: number | null; // meters
  duration?: number | null; // seconds
  movingDuration?: number | null;
  elapsedDuration?: number | null;
  averageSpeed?: number | null; // m/s
  maxSpeed?: number | null; // m/s
  averageHR?: number | null;
  maxHR?: number | null;
  averageRunCadence?: number | null;
  elevationGain?: number | null;
  calories?: number | null;
  [key: string]: unknown;
}

export interface ActivityDetail extends ActivitySummary {
  garmin_activity_id?: string | null;
  start_time?: string | null;
  max_hr?: number | null;
  calories?: number | null;
  created_at?: string | null;
  raw?: Record<string, unknown> | null;
  laps?: ActivityLap[] | null;
}

export type TrackingStatus =
  | "completed"
  | "missed"
  | "rest"
  | "upcoming"
  | "extra";

export interface TrackingDay {
  date: string;
  weekday: number;
  weekday_name: string;
  planned: PlannedWorkout[];
  actual: ActivitySummary[];
  status: TrackingStatus;
}

export interface TrackingWeek {
  plan_id: number;
  version_id: number;
  week_no: number;
  num_weeks: number;
  current_week: number;
  week_start: string;
  week_end: string;
  days: TrackingDay[];
}

export interface PlanInputs {
  title?: string | null;
  distance_label: string;
  distance_m?: number | null;
  target_date: string;
  goal_type: "time" | "pace" | "finish";
  goal_value?: string | null;
  is_race: boolean;
  current_weekly_volume?: string | null;
  training_frequency_days?: number | null;
  experience_level?: string | null;
  days_available: string[];
  time_per_session?: string | null;
  time_per_session_by_day: Record<string, string>;
  preferred_long_run_day?: string | null;
  strength_work?: string | null;
  other_sports?: string | null;
  mobility_prehab?: string | null;
  longest_run_last_month_km?: number | null;
  vo2max?: number | null;
  resting_hr?: number | null;
  max_hr?: number | null;
  threshold_hr?: number | null;
  training_load?: string | null;
  include_activity_history: boolean;
  activity_history_start?: string | null;
  activity_history_end?: string | null;
  extra_notes?: string | null;
}

export interface WeeklyUpdateResult {
  update_recommended: boolean;
  proposed_version_id?: number | null;
  change_summary?: string | null;
  message?: string | null;
}

// --- Live AI processing stream ---

export interface DoneEvent {
  type: "done";
  plan_id: number;
  version_id?: number;
  update_recommended?: boolean;
  proposed_version_id?: number | null;
  change_summary?: string | null;
  message?: string | null;
}

export type AIProcessingEvent =
  | { type: "prompt"; system: string; user: string }
  | { type: "thinking"; delta: string }
  | { type: "text"; delta: string }
  | { type: "step"; label: string }
  | DoneEvent
  | { type: "error"; message: string };

/** Accumulated record of one agent run, rendered live and re-openable later. */
export interface AITrace {
  prompt?: { system: string; user: string };
  thinking: string;
  text: string;
  steps: string[];
  status: "running" | "done" | "error";
  error?: string;
}
