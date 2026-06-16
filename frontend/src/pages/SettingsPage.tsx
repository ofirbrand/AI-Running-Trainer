import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { Banner, Field, PageLoader, Spinner } from "../components/ui";
import { InfoTip } from "../components/InfoTip";
import { titleCase } from "../lib/format";

export function SettingsPage() {
  const qc = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
  });
  const { data: options } = useQuery({
    queryKey: ["settings-options"],
    queryFn: settingsApi.options,
  });

  const [model, setModel] = useState("");
  const [effort, setEffort] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (settings) {
      setModel(settings.ai_model);
      setEffort(settings.reasoning_effort);
    }
  }, [settings]);

  const mutation = useMutation({
    mutationFn: () => settingsApi.update({ ai_model: model, reasoning_effort: effort }),
    onSuccess: () => {
      setSaved(true);
      void qc.invalidateQueries({ queryKey: ["settings"] });
      setTimeout(() => setSaved(false), 2500);
    },
  });

  if (isLoading) return <PageLoader />;

  const models = options?.models ?? [model];
  const efforts = options?.reasoning_efforts ?? ["minimal", "low", "medium", "high"];

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
      <div className="card p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-800">AI model</h2>
        {mutation.isError && <Banner kind="error">{apiErrorMessage(mutation.error)}</Banner>}
        {saved && <Banner kind="success">Settings saved.</Banner>}
        <div className="mt-2 space-y-4">
          <Field label="Model" htmlFor="model" hint="Which Claude model creates and updates your plans.">
            <select id="model" className="input" value={model} onChange={(e) => setModel(e.target.value)}>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Reasoning effort"
            htmlFor="effort"
            info={<InfoTip term="reasoning_effort" />}
          >
            <select
              id="effort"
              className="input"
              value={effort}
              onChange={(e) => setEffort(e.target.value)}
            >
              {efforts.map((e) => (
                <option key={e} value={e}>
                  {titleCase(e)}
                </option>
              ))}
            </select>
          </Field>
          <button className="btn-primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending && <Spinner />} Save settings
          </button>
        </div>
      </div>
    </div>
  );
}
