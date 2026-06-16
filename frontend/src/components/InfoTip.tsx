import * as Popover from "@radix-ui/react-popover";
import { Info } from "lucide-react";
import { infoFor } from "../lib/info";

interface InfoTipProps {
  /** Key into the shared info dictionary, or pass `text` directly. */
  term?: string;
  text?: string;
  label?: string;
}

/**
 * A small "i" information component. Content is bundled client-side so it opens
 * instantly with no network latency. Matches the app's visual style.
 */
export function InfoTip({ term, text, label }: InfoTipProps) {
  const content = text ?? (term ? infoFor(term) : undefined);
  if (!content) return null;

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label={label ?? "More information"}
          className="inline-flex h-4 w-4 items-center justify-center rounded-full text-slate-400 transition-colors hover:text-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-300"
        >
          <Info className="h-4 w-4" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="top"
          align="center"
          sideOffset={6}
          className="z-50 max-w-xs rounded-lg border border-slate-200 bg-white p-3 text-xs leading-relaxed text-slate-600 shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0"
        >
          {content}
          <Popover.Arrow className="fill-white" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
