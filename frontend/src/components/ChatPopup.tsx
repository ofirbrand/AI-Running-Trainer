import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Send, Sparkles, X } from "lucide-react";
import clsx from "clsx";
import { plansApi } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { Spinner } from "./ui";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function ChatPopup({
  planId,
  open,
  onOpenChange,
  onConfirm,
}: {
  planId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (requests: string[]) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Tell me what you'd like to change about this plan — for example pace targets, which days you run, the long-run day, or anything else. When you're done, click \"Regenerate plan\".",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const userMessages = messages.filter((m) => m.role === "user").map((m) => m.content);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    const next = [...messages, { role: "user" as const, content: text }];
    setMessages(next);
    setInput("");
    setSending(true);
    setError(null);
    try {
      const reply = await plansApi.chat(
        planId,
        next.map((m) => ({ role: m.role, content: m.content })),
      );
      setMessages((prev) => [...prev, { role: "assistant", content: reply.content }]);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  function confirm() {
    if (userMessages.length === 0) {
      setError("Describe at least one change before regenerating.");
      return;
    }
    setError(null);
    onConfirm(userMessages);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex h-[600px] max-h-[90vh] w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <Dialog.Title className="flex items-center gap-2 font-semibold text-slate-900">
              <Sparkles className="h-5 w-5 text-brand-600" /> Request changes
            </Dialog.Title>
            <Dialog.Close className="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
            {messages.map((m, i) => (
              <div
                key={i}
                className={clsx("flex", m.role === "user" ? "justify-end" : "justify-start")}
              >
                <div
                  className={clsx(
                    "max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm",
                    m.role === "user"
                      ? "bg-brand-600 text-white"
                      : "bg-slate-100 text-slate-700",
                  )}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-slate-100 px-4 py-2 text-slate-400">
                  <Spinner />
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="px-5 pb-2 text-sm text-red-600">{error}</div>
          )}

          <div className="border-t border-slate-200 px-5 py-3">
            <div className="flex items-end gap-2">
              <textarea
                className="input min-h-[44px] resize-none"
                rows={1}
                placeholder="Describe a change…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
              />
              <button
                className="btn-secondary h-[44px]"
                onClick={() => void send()}
                disabled={sending || !input.trim()}
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            <button
              className="btn-primary mt-3 w-full"
              onClick={confirm}
              disabled={userMessages.length === 0}
            >
              <Sparkles className="h-4 w-4" /> These are all my changes — regenerate plan
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
