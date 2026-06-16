import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, RefreshCw, Watch } from "lucide-react";
import { garminApi } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { Banner, Field, Spinner } from "./ui";
import { InfoTip } from "./InfoTip";
import { formatDate } from "../lib/format";

export function GarminConnect({ onConnected }: { onConnected?: () => void }) {
  const qc = useQueryClient();
  const { data: status, isLoading } = useQuery({
    queryKey: ["garmin-status"],
    queryFn: garminApi.status,
  });

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function connect() {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await garminApi.connect({
        garmin_email: email,
        password,
        mfa_code: mfaRequired ? mfaCode : undefined,
      });
      if (res.mfa_required) {
        setMfaRequired(true);
        setBusy(false);
        return;
      }
      setSuccess("Garmin connected and synced.");
      setMfaRequired(false);
      setPassword("");
      setMfaCode("");
      await qc.invalidateQueries({ queryKey: ["garmin-status"] });
      onConnected?.();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function sync() {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await garminApi.sync();
      setSuccess(
        `Synced ${res.activities_synced} activities, ${res.days_health_synced} days of health data.`,
      );
      await qc.invalidateQueries({ queryKey: ["garmin-status"] });
      await qc.invalidateQueries({ queryKey: ["prefill"] });
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    try {
      await garminApi.disconnect();
      await qc.invalidateQueries({ queryKey: ["garmin-status"] });
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <Spinner />;

  if (status?.connected) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-brand-700">
          <CheckCircle2 className="h-5 w-5" />
          <span className="font-medium">Connected as {status.garmin_email}</span>
        </div>
        <p className="text-sm text-slate-500">
          Last sync: {status.last_sync_at ? formatDate(status.last_sync_at) : "never"}
        </p>
        {status.last_sync_error && <Banner kind="warning">{status.last_sync_error}</Banner>}
        {success && <Banner kind="success">{success}</Banner>}
        {error && <Banner kind="error">{error}</Banner>}
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => void sync()} disabled={busy}>
            {busy ? <Spinner /> : <RefreshCw className="h-4 w-4" />} Sync now
          </button>
          <button className="btn-ghost" onClick={() => void disconnect()} disabled={busy}>
            Disconnect
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-slate-700">
        <Watch className="h-5 w-5 text-brand-600" />
        <span className="font-medium">Connect your Garmin account</span>
        <InfoTip term="garmin_connect" />
      </div>
      {error && <Banner kind="error">{error}</Banner>}
      {!mfaRequired ? (
        <>
          <Field label="Garmin email" htmlFor="g-email">
            <input
              id="g-email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="off"
            />
          </Field>
          <Field label="Garmin password" htmlFor="g-pass">
            <input
              id="g-pass"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="off"
            />
          </Field>
        </>
      ) : (
        <Field label="Authenticator code" htmlFor="g-mfa" hint="Enter the 6-digit code from your authenticator or SMS.">
          <input
            id="g-mfa"
            className="input"
            inputMode="numeric"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value)}
          />
        </Field>
      )}
      <button
        className="btn-primary w-full"
        onClick={() => void connect()}
        disabled={busy || (!mfaRequired && (!email || !password))}
      >
        {busy ? <Spinner /> : null}
        {mfaRequired ? "Verify code" : "Connect Garmin"}
      </button>
      <p className="text-xs text-slate-400">
        We never store your Garmin password — only a refreshable session token, saved locally on
        this machine.
      </p>
    </div>
  );
}
