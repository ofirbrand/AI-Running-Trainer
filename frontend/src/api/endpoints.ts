import { api } from "./client";
import type {
  ActivityDetail,
  ActivityFetchResult,
  ActivitySummary,
  GarminHealth,
  GarminStatus,
  Metric,
  PlanDetail,
  PlanInputs,
  PlanSummary,
  PlanVersion,
  Profile,
  Settings,
  SyncResult,
  TrackingWeek,
  WeeklyUpdateResult,
} from "./types";

// --- Auth ---
export const authApi = {
  register: (body: { email: string; password: string; profile: Partial<Profile> }) =>
    api.post<{ access_token: string }>("/auth/register", body).then((r) => r.data),
  login: (email: string, password: string) =>
    api.post<{ access_token: string }>("/auth/login", { email, password }).then((r) => r.data),
};

// --- Profile ---
export const profileApi = {
  get: () => api.get<Profile>("/profile").then((r) => r.data),
  update: (body: Profile) => api.put<Profile>("/profile", body).then((r) => r.data),
};

// --- Garmin ---
export const garminApi = {
  status: () => api.get<GarminStatus>("/garmin/status").then((r) => r.data),
  connect: (body: { garmin_email: string; password: string; mfa_code?: string }) =>
    api
      .post<{ connected?: boolean; mfa_required?: boolean; sync?: SyncResult }>(
        "/garmin/connect",
        body,
      )
      .then((r) => r.data),
  disconnect: () => api.post<GarminStatus>("/garmin/disconnect").then((r) => r.data),
  sync: () => api.post<SyncResult>("/garmin/sync").then((r) => r.data),
  health: (date?: string) =>
    api
      .get<GarminHealth>("/garmin/health", { params: date ? { date } : {} })
      .then((r) => r.data),
  activities: (params?: { start?: string; end?: string; limit?: number }) =>
    api.get<ActivitySummary[]>("/garmin/activities", { params }).then((r) => r.data),
  activity: (id: number) =>
    api.get<ActivityDetail>(`/garmin/activities/${id}`).then((r) => r.data),
  fetchActivities: (start: string, end: string) =>
    api
      .post<ActivityFetchResult>("/garmin/activities/fetch", { start, end })
      .then((r) => r.data),
  metrics: () => api.get<Metric[]>("/garmin/metrics").then((r) => r.data),
  upsertMetric: (body: { key: string; value: unknown; unit?: string; measured_at?: string }) =>
    api.put<Metric>("/garmin/metrics", body).then((r) => r.data),
};

// --- Settings ---
export const settingsApi = {
  get: () => api.get<Settings>("/settings").then((r) => r.data),
  update: (body: Settings) => api.put<Settings>("/settings", body).then((r) => r.data),
  options: () =>
    api
      .get<{ models: string[]; reasoning_efforts: string[] }>("/settings/options")
      .then((r) => r.data),
};

// --- Plans ---
export interface PrefillResponse {
  profile: Profile;
  metrics: Metric[];
  prefill: Record<string, { value: unknown; unit?: string; source?: string; measured_at?: string }>;
  has_previous_plan: boolean;
}

export const plansApi = {
  list: () => api.get<PlanSummary[]>("/plans").then((r) => r.data),
  prefill: () => api.get<PrefillResponse>("/plans/prefill").then((r) => r.data),
  create: (inputs: PlanInputs) => api.post<PlanDetail>("/plans", inputs).then((r) => r.data),
  get: (planId: number) => api.get<PlanDetail>(`/plans/${planId}`).then((r) => r.data),
  version: (planId: number, versionId: number) =>
    api.get<PlanVersion>(`/plans/${planId}/versions/${versionId}`).then((r) => r.data),
  approve: (planId: number, versionId: number) =>
    api.post<PlanDetail>(`/plans/${planId}/versions/${versionId}/approve`).then((r) => r.data),
  restore: (planId: number, versionId: number) =>
    api.post<PlanDetail>(`/plans/${planId}/versions/${versionId}/restore`).then((r) => r.data),
  chat: (planId: number, messages: { role: string; content: string }[]) =>
    api
      .post<{ role: "assistant"; content: string }>(`/plans/${planId}/chat`, { messages })
      .then((r) => r.data),
  confirmChanges: (planId: number, requests: string[]) =>
    api
      .post<WeeklyUpdateResult>(`/plans/${planId}/confirm-changes`, { requests })
      .then((r) => r.data),
  weeklyUpdate: (planId: number) =>
    api.post<WeeklyUpdateResult>(`/plans/${planId}/weekly-update`).then((r) => r.data),
  manualUpdate: (planId: number, requestText: string) =>
    api
      .post<WeeklyUpdateResult>(`/plans/${planId}/manual-update`, { request_text: requestText })
      .then((r) => r.data),
  tracking: (planId: number, weekNo?: number) =>
    api
      .get<TrackingWeek>(`/plans/${planId}/tracking`, {
        params: weekNo ? { week_no: weekNo } : {},
      })
      .then((r) => r.data),
};

export type { ActivitySummary };
