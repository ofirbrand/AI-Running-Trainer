import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronRight, Plus, Target, Trophy } from "lucide-react";
import { garminApi, plansApi } from "../api/endpoints";
import { Badge, Banner, PageLoader } from "../components/ui";
import { formatDate, relativeDay } from "../lib/format";
import type { PlanSummary } from "../api/types";

function statusBadge(status: string) {
  if (status === "active") return <Badge color="green">Active</Badge>;
  if (status === "draft") return <Badge color="amber">Draft</Badge>;
  return <Badge color="slate">{status}</Badge>;
}

function PlanCard({ plan }: { plan: PlanSummary }) {
  const to = plan.status === "draft" ? `/plans/${plan.id}` : `/plans/${plan.id}/tracking`;
  return (
    <Link
      to={to}
      className="card group flex items-center justify-between p-5 transition-shadow hover:shadow-md"
    >
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-slate-900">{plan.title}</h3>
          {plan.is_race && <Trophy className="h-4 w-4 text-amber-500" />}
          {statusBadge(plan.status)}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
          {plan.target_date && (
            <span className="flex items-center gap-1">
              <CalendarDays className="h-4 w-4" /> {formatDate(plan.target_date)} (
              {relativeDay(plan.target_date)})
            </span>
          )}
          {plan.goal_value && (
            <span className="flex items-center gap-1">
              <Target className="h-4 w-4" /> {plan.goal_value}
            </span>
          )}
        </div>
      </div>
      <ChevronRight className="h-5 w-5 text-slate-300 transition-transform group-hover:translate-x-1 group-hover:text-brand-600" />
    </Link>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { data: plans, isLoading } = useQuery({ queryKey: ["plans"], queryFn: plansApi.list });
  const { data: garmin } = useQuery({ queryKey: ["garmin-status"], queryFn: garminApi.status });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Your training plans</h1>
          <p className="text-sm text-slate-500">Build, track, and refine your running plans.</p>
        </div>
        <button className="btn-primary" onClick={() => navigate("/plans/new")}>
          <Plus className="h-4 w-4" /> Add training plan
        </button>
      </div>

      {garmin && !garmin.connected && (
        <Banner kind="warning">
          Garmin isn't connected.{" "}
          <Link to="/profile" className="font-semibold underline">
            Connect it
          </Link>{" "}
          so your plan and tracking use real data.
        </Banner>
      )}

      {isLoading ? (
        <PageLoader />
      ) : plans && plans.length > 0 ? (
        <div className="grid gap-3">
          {plans.map((p) => (
            <PlanCard key={p.id} plan={p} />
          ))}
        </div>
      ) : (
        <div className="card flex flex-col items-center justify-center gap-3 p-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
            <Plus className="h-6 w-6" />
          </div>
          <h3 className="font-semibold text-slate-800">No plans yet</h3>
          <p className="max-w-sm text-sm text-slate-500">
            Create your first AI-built training plan. We'll use your profile and Garmin data to
            tailor it to your goal.
          </p>
          <button className="btn-primary" onClick={() => navigate("/plans/new")}>
            <Plus className="h-4 w-4" /> Create a plan
          </button>
        </div>
      )}
    </div>
  );
}
