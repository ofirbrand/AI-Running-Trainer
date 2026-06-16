import clsx from "clsx";
import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx("h-4 w-4 animate-spin", className)} />;
}

export function PageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-3 text-slate-400">
      <Spinner className="h-6 w-6" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function Banner({
  kind = "info",
  children,
}: {
  kind?: "info" | "error" | "success" | "warning";
  children: ReactNode;
}) {
  const styles = {
    info: "bg-blue-50 text-blue-800 border-blue-200",
    error: "bg-red-50 text-red-800 border-red-200",
    success: "bg-brand-50 text-brand-800 border-brand-200",
    warning: "bg-amber-50 text-amber-800 border-amber-200",
  }[kind];
  return (
    <div className={clsx("rounded-lg border px-4 py-3 text-sm", styles)}>{children}</div>
  );
}

export function Badge({
  children,
  color = "slate",
}: {
  children: ReactNode;
  color?: "slate" | "green" | "red" | "amber" | "blue" | "purple";
}) {
  const styles = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-brand-100 text-brand-800",
    red: "bg-red-100 text-red-700",
    amber: "bg-amber-100 text-amber-800",
    blue: "bg-blue-100 text-blue-700",
    purple: "bg-purple-100 text-purple-700",
  }[color];
  return <span className={clsx("badge", styles)}>{children}</span>;
}

export function Field({
  label,
  htmlFor,
  info,
  children,
  hint,
}: {
  label: string;
  htmlFor?: string;
  info?: ReactNode;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <div>
      <label className="label" htmlFor={htmlFor}>
        {label}
        {info}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}
