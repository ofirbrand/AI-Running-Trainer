import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity } from "lucide-react";
import { authApi } from "../api/endpoints";
import { setToken } from "../api/client";
import { apiErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Banner, Field, Spinner } from "../components/ui";
import { EMPTY_PROFILE, ProfileForm } from "../components/ProfileForm";
import type { Profile } from "../api/types";

export function RegisterPage() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [profile, setProfile] = useState<Profile>({ ...EMPTY_PROFILE });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function next(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setError(null);
    setStep(2);
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const { access_token } = await authApi.register({ email, password, profile });
      setToken(access_token);
      await refresh();
      navigate("/connect");
    } catch (err) {
      setError(apiErrorMessage(err, "Registration failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-brand-50 to-slate-50 px-4 py-10">
      <div className="card w-full max-w-2xl p-8">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Activity className="h-7 w-7" />
          </span>
          <h1 className="text-2xl font-bold text-slate-900">Create your account</h1>
          <p className="text-sm text-slate-500">
            Step {step} of 2 — {step === 1 ? "account" : "your runner profile"}
          </p>
        </div>

        {error && <Banner kind="error">{error}</Banner>}

        {step === 1 ? (
          <form onSubmit={next} className="mt-4 space-y-4">
            <Field label="Email" htmlFor="email">
              <input
                id="email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </Field>
            <Field label="Password" htmlFor="password" hint="At least 8 characters.">
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </Field>
            <button className="btn-primary w-full">Continue</button>
          </form>
        ) : (
          <div className="mt-4 space-y-6">
            <ProfileForm value={profile} onChange={setProfile} />
            <div className="flex gap-2">
              <button className="btn-secondary" onClick={() => setStep(1)} disabled={busy}>
                Back
              </button>
              <button className="btn-primary flex-1" onClick={() => void submit()} disabled={busy}>
                {busy && <Spinner />} Create account & connect Garmin
              </button>
            </div>
          </div>
        )}

        <p className="mt-6 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
