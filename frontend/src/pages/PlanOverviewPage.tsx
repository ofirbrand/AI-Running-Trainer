import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import {
  CalendarDays,
  CheckCircle2,
  GitCompareArrows,
  History,
  LineChart,
  MessageSquarePlus,
  RefreshCw,
  ScrollText,
  Sparkles,
  Target,
  Trophy,
  X,
} from "lucide-react";
import { plansApi } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { Badge, Banner, PageLoader, Spinner } from "../components/ui";
import { WeeklyTable } from "../components/WeeklyTable";
import { PlanDiff } from "../components/PlanDiff";
import { ChatPopup } from "../components/ChatPopup";
import { AIProcessingModal, useAIProcessing } from "../components/AIProcessingStream";
import { useHasTrace } from "../state/aiProcessingStore";
import { InfoTip } from "../components/InfoTip";
import { formatDate, relativeDay, titleCase } from "../lib/format";
import type { PlanDetail, PlanVersion } from "../api/types";

export function PlanOverviewPage() {
  const { id } = useParams();
  const planId = Number(id);
  const qc = useQueryClient();

  const { data: plan, isLoading } = useQuery({
    queryKey: ["plan", planId],
    queryFn: () => plansApi.get(planId),
  });

  const [chatOpen, setChatOpen] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [dismissedProposed, setDismissedProposed] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const ai = useAIProcessing();
  const hasTrace = useHasTrace(planId);

  const refetch = () => qc.invalidateQueries({ queryKey: ["plan", planId] });

  async function runWeekly() {
    try {
      const done = await ai.run(`/plans/${planId}/weekly-update/stream`);
      if (done.update_recommended) {
        setDismissedProposed(null);
        void refetch();
      } else {
        setNotice(done.message ?? "No changes recommended.");
      }
    } catch {
      /* error surfaced in the AI processing modal */
    }
  }

  async function runManual(text: string) {
    setManualOpen(false);
    try {
      await ai.run(`/plans/${planId}/manual-update/stream`, { request_text: text });
      setDismissedProposed(null);
      void refetch();
    } catch {
      /* error surfaced in the AI processing modal */
    }
  }

  async function runConfirm(requests: string[]) {
    setChatOpen(false);
    try {
      await ai.run(`/plans/${planId}/confirm-changes/stream`, { requests });
      setDismissedProposed(null);
      void refetch();
    } catch {
      /* error surfaced in the AI processing modal */
    }
  }

  const activeVersion = useMemo(
    () => plan?.versions.find((v) => v.status === "active") ?? plan?.active_version ?? null,
    [plan],
  );
  const latestVersion = useMemo(
    () => (plan && plan.versions.length ? plan.versions[plan.versions.length - 1] : null),
    [plan],
  );
  const proposed = useMemo(
    () => plan?.versions.filter((v) => v.status === "proposed").slice(-1)[0] ?? null,
    [plan],
  );

  const approve = useMutation({
    mutationFn: (versionId: number) => plansApi.approve(planId, versionId),
    onSuccess: () => {
      setNotice(null);
      void refetch();
    },
  });

  if (isLoading || !plan) return <PageLoader />;

  const isInitialDraft = !activeVersion && latestVersion?.status === "draft";
  const displayVersion = activeVersion ?? latestVersion;
  const showProposedReview = proposed && proposed.id !== dismissedProposed && activeVersion;

  return (
    <div className="space-y-6">
      <PlanHeader plan={plan} />

      {/* Proposed update review */}
      {showProposedReview && activeVersion && proposed && (
        <div className="card border-brand-300 p-6">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-brand-600" />
            <h2 className="text-lg font-semibold text-slate-800">Proposed plan update</h2>
            <Badge color="purple">{titleCase(proposed.source)}</Badge>
          </div>
          {proposed.change_summary && (
            <Banner kind="info">{proposed.change_summary}</Banner>
          )}
          <div className="mt-4">
            <PlanDiff left={activeVersion} right={proposed} />
          </div>
          <div className="mt-5 flex gap-2">
            <button
              className="btn-primary"
              onClick={() => approve.mutate(proposed.id)}
              disabled={approve.isPending}
            >
              {approve.isPending ? <Spinner /> : <CheckCircle2 className="h-4 w-4" />} Approve update
            </button>
            <button className="btn-secondary" onClick={() => setDismissedProposed(proposed.id)}>
              Keep current plan
            </button>
          </div>
        </div>
      )}

      {notice && <Banner kind="info">{notice}</Banner>}

      {/* Explanations */}
      {displayVersion && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card p-6">
            <h2 className="mb-2 text-lg font-semibold text-slate-800">How this plan is built</h2>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-600">
              {displayVersion.structure_explanation}
            </p>
          </div>
          <div className="card p-6">
            <h2 className="mb-2 text-lg font-semibold text-slate-800">Plan overview</h2>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-600">
              {displayVersion.full_explanation}
            </p>
          </div>
        </div>
      )}

      {/* Workout types */}
      {displayVersion?.workout_types && displayVersion.workout_types.length > 0 && (
        <div className="card p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Workout types</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {displayVersion.workout_types.map((wt) => (
              <div key={wt.name} className="rounded-lg bg-slate-50 p-3">
                <p className="text-sm font-semibold text-slate-700">{wt.name}</p>
                <p className="mt-0.5 text-xs text-slate-500">{wt.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Weekly table */}
      {displayVersion && (
        <div className="card p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-800">
              Weekly schedule
              <span className="ml-2 text-sm font-normal text-slate-400">
                (version {displayVersion.version_no})
              </span>
            </h2>
            {activeVersion && (
              <Link className="btn-secondary" to={`/plans/${planId}/tracking`}>
                <LineChart className="h-4 w-4" /> Track progress
              </Link>
            )}
          </div>
          <WeeklyTable version={displayVersion} />
        </div>
      )}

      {approve.isError && <Banner kind="error">{apiErrorMessage(approve.error)}</Banner>}

      {/* Action bar */}
      <div className="card flex flex-wrap items-center gap-3 p-5">
        {isInitialDraft && latestVersion ? (
          <>
            <p className="mr-auto text-sm text-slate-600">
              Review your plan, then approve it to start tracking — or request changes.
            </p>
            <button className="btn-secondary" onClick={() => setChatOpen(true)}>
              <MessageSquarePlus className="h-4 w-4" /> Request changes
            </button>
            <button
              className="btn-primary"
              onClick={() => approve.mutate(latestVersion.id)}
              disabled={approve.isPending}
            >
              {approve.isPending ? <Spinner /> : <CheckCircle2 className="h-4 w-4" />} Approve plan
            </button>
          </>
        ) : (
          <>
            <p className="mr-auto text-sm font-medium text-slate-700">Update training plan</p>
            <UpdateMenu
              running={ai.open && ai.trace.status === "running"}
              hasTrace={hasTrace}
              onWeekly={() => void runWeekly()}
              onOpenManual={() => setManualOpen(true)}
              onOpenVersions={() => setVersionsOpen(true)}
              onRequestChat={() => setChatOpen(true)}
              onViewProcessing={() => ai.replay(planId)}
            />
          </>
        )}
      </div>

      <ChatPopup
        planId={planId}
        open={chatOpen}
        onOpenChange={setChatOpen}
        onConfirm={(requests) => void runConfirm(requests)}
      />

      <ManualUpdateDialog
        open={manualOpen}
        onOpenChange={setManualOpen}
        onSubmit={(text) => void runManual(text)}
      />

      <AIProcessingModal trace={ai.trace} open={ai.open} onOpenChange={ai.setOpen} />

      <VersionsDialog
        plan={plan}
        open={versionsOpen}
        onOpenChange={setVersionsOpen}
        onRestored={() => {
          setVersionsOpen(false);
          void refetch();
        }}
      />
    </div>
  );
}

function PlanHeader({ plan }: { plan: PlanDetail }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-slate-900">{plan.title}</h1>
          {plan.is_race && <Trophy className="h-5 w-5 text-amber-500" />}
          <Badge color={plan.status === "active" ? "green" : "amber"}>{titleCase(plan.status)}</Badge>
        </div>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
          {plan.target_date && (
            <span className="flex items-center gap-1">
              <CalendarDays className="h-4 w-4" /> {formatDate(plan.target_date)} (
              {relativeDay(plan.target_date)})
            </span>
          )}
          {plan.goal_value && (
            <span className="flex items-center gap-1">
              <Target className="h-4 w-4" /> {titleCase(plan.goal_type)}: {plan.goal_value}
            </span>
          )}
        </div>
      </div>
      <Link to="/" className="btn-ghost">
        Back to plans
      </Link>
    </div>
  );
}

function UpdateMenu({
  running,
  hasTrace,
  onWeekly,
  onOpenManual,
  onOpenVersions,
  onRequestChat,
  onViewProcessing,
}: {
  running: boolean;
  hasTrace: boolean;
  onWeekly: () => void;
  onOpenManual: () => void;
  onOpenVersions: () => void;
  onRequestChat: () => void;
  onViewProcessing: () => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <button className="btn-secondary" onClick={onWeekly} disabled={running}>
        {running ? <Spinner /> : <RefreshCw className="h-4 w-4" />} Weekly review
        <InfoTip text="Reviews the workouts you actually completed this week and proposes an updated plan if helpful." />
      </button>
      <button className="btn-secondary" onClick={onOpenManual} disabled={running}>
        <Sparkles className="h-4 w-4" /> Change details
      </button>
      <button className="btn-secondary" onClick={onRequestChat} disabled={running}>
        <MessageSquarePlus className="h-4 w-4" /> Chat with coach
      </button>
      <button className="btn-secondary" onClick={onOpenVersions}>
        <History className="h-4 w-4" /> Versions
      </button>
      {hasTrace && (
        <button className="btn-secondary" onClick={onViewProcessing}>
          <ScrollText className="h-4 w-4" /> View AI processing
        </button>
      )}
    </div>
  );
}

function ManualUpdateDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSubmit: (text: string) => void;
}) {
  const [text, setText] = useState("");

  function submit() {
    const value = text.trim();
    if (!value) return;
    setText("");
    onSubmit(value);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-6 shadow-xl">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="flex items-center gap-2 font-semibold text-slate-900">
              <Sparkles className="h-5 w-5 text-brand-600" /> Change plan details
            </Dialog.Title>
            <Dialog.Close className="rounded-lg p-1 text-slate-400 hover:bg-slate-100">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>
          <p className="mb-3 text-sm text-slate-500">
            Describe what to change — e.g. "push the race to Oct 12", "drop to 4 days a week", or
            "I'm on vacation June 20-28, no running".
          </p>
          <textarea
            className="input min-h-[120px]"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Describe your change…"
          />
          <div className="mt-4 flex justify-end gap-2">
            <Dialog.Close className="btn-secondary">Cancel</Dialog.Close>
            <button className="btn-primary" onClick={submit} disabled={!text.trim()}>
              <Sparkles className="h-4 w-4" /> Generate update
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function VersionsDialog({
  plan,
  open,
  onOpenChange,
  onRestored,
}: {
  plan: PlanDetail;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onRestored: () => void;
}) {
  const versions = [...plan.versions].sort((a, b) => b.version_no - a.version_no);
  const [leftId, setLeftId] = useState<number | null>(plan.active_version_id ?? null);
  const [rightId, setRightId] = useState<number | null>(
    versions.length > 1 ? versions[0].id : null,
  );

  const left = versions.find((v) => v.id === leftId) ?? null;
  const right = versions.find((v) => v.id === rightId) ?? null;

  const restore = useMutation({
    mutationFn: (versionId: number) => plansApi.restore(plan.id, versionId),
    onSuccess: onRestored,
  });

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[94vw] max-w-4xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="flex items-center gap-2 font-semibold text-slate-900">
              <GitCompareArrows className="h-5 w-5 text-brand-600" /> Compare & restore versions
            </Dialog.Title>
            <Dialog.Close className="rounded-lg p-1 text-slate-400 hover:bg-slate-100">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>

          <div className="mb-4 grid grid-cols-2 gap-4">
            <VersionPicker label="Left" versions={versions} value={leftId} onChange={setLeftId} activeId={plan.active_version_id} />
            <VersionPicker label="Right" versions={versions} value={rightId} onChange={setRightId} activeId={plan.active_version_id} />
          </div>

          {restore.isError && <Banner kind="error">{apiErrorMessage(restore.error)}</Banner>}

          {left && right ? (
            <PlanDiff
              left={left}
              right={right}
              leftTitle={`Version ${left.version_no}`}
              rightTitle={`Version ${right.version_no}`}
            />
          ) : (
            <p className="text-sm text-slate-400">Pick two versions to compare.</p>
          )}

          <div className="mt-5 flex justify-end gap-2">
            {right && right.id !== plan.active_version_id && (
              <button
                className="btn-primary"
                onClick={() => restore.mutate(right.id)}
                disabled={restore.isPending}
              >
                {restore.isPending ? <Spinner /> : <History className="h-4 w-4" />} Make version{" "}
                {right.version_no} active
              </button>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function VersionPicker({
  label,
  versions,
  value,
  onChange,
  activeId,
}: {
  label: string;
  versions: PlanVersion[];
  value: number | null;
  onChange: (id: number) => void;
  activeId?: number | null;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <select
        className="input"
        value={value ?? ""}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        <option value="">Select…</option>
        {versions.map((v) => (
          <option key={v.id} value={v.id}>
            v{v.version_no} · {titleCase(v.source)}
            {v.id === activeId ? " (active)" : ""} · {formatDate(v.created_at)}
          </option>
        ))}
      </select>
    </div>
  );
}
