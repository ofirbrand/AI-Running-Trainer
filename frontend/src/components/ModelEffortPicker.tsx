import * as Popover from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import clsx from "clsx";
import { settingsApi } from "../api/endpoints";
import { titleCase } from "../lib/format";

/** "claude-opus-4-8" -> "Opus 4.8" */
function modelDisplayName(id: string): string {
  const parts = id.replace(/^claude-/, "").split("-");
  if (parts.length === 0 || !parts[0]) return id;
  const family = parts[0][0].toUpperCase() + parts[0].slice(1);
  const version = parts.slice(1).join(".");
  return version ? `${family} ${version}` : family;
}

function effortShort(effort: string): string {
  return effort === "medium" ? "Med" : titleCase(effort);
}

/**
 * Compact model + reasoning-effort picker for the Plan Workout header.
 * `null` means "use my settings default"; a picked value is a session-only
 * override — it is sent with the generate request and never saved.
 */
export function ModelEffortPicker({
  model,
  effort,
  onChange,
  disabled,
}: {
  model: string | null;
  effort: string | null;
  onChange: (model: string | null, effort: string | null) => void;
  disabled?: boolean;
}) {
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: settingsApi.get });
  const { data: options } = useQuery({
    queryKey: ["settings-options"],
    queryFn: settingsApi.options,
  });

  const effectiveModel = model ?? settings?.ai_model ?? "";
  const effectiveEffort = effort ?? settings?.reasoning_effort ?? "";
  const models = options?.models ?? [];
  const efforts = options?.reasoning_efforts ?? ["low", "medium", "high", "max"];

  const pill = (selected: boolean) =>
    clsx(
      "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
      selected
        ? "border-brand-600 bg-brand-600 text-white"
        : "border-slate-200 bg-white text-slate-600 hover:border-brand-300 hover:text-brand-700",
    );

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          disabled={disabled}
          className="flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 transition-colors hover:border-brand-300 hover:text-brand-700 disabled:opacity-50"
          aria-label="Choose AI model and reasoning effort"
        >
          {effectiveModel ? modelDisplayName(effectiveModel) : "Model"}
          {effectiveEffort ? ` · ${effortShort(effectiveEffort)}` : ""}
          <ChevronDown className="h-3 w-3" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="end"
          sideOffset={6}
          className="z-[60] w-64 rounded-xl border border-slate-200 bg-white p-4 shadow-lg"
        >
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Model
          </p>
          <div className="flex flex-wrap gap-2">
            {(models.length > 0 ? models : [effectiveModel].filter(Boolean)).map((m) => (
              <button
                key={m}
                type="button"
                className={pill(m === effectiveModel)}
                onClick={() => onChange(m, effort)}
              >
                {modelDisplayName(m)}
              </button>
            ))}
          </div>
          <p className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Reasoning effort
          </p>
          <div className="flex flex-wrap gap-2">
            {efforts.map((e) => (
              <button
                key={e}
                type="button"
                className={pill(e === effectiveEffort)}
                onClick={() => onChange(model, e)}
              >
                {titleCase(e)}
              </button>
            ))}
          </div>
          <p className="mt-4 text-[11px] leading-snug text-slate-400">
            Applies to this workout only — it doesn't change your settings.
          </p>
          <Popover.Arrow className="fill-white" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
