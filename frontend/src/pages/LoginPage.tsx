import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { apiErrorMessage } from "../api/client";
import { Banner, Field, Spinner } from "../components/ui";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(apiErrorMessage(err, "Login failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-brand-50 to-slate-50 px-4">
      <div className="card w-full max-w-md p-8">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Activity className="h-7 w-7" />
          </span>
          <h1 className="text-2xl font-bold text-slate-900">Welcome back</h1>
          <p className="text-sm text-slate-500">Sign in to your AI Running Coach</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          {error && <Banner kind="error">{error}</Banner>}
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
          <Field label="Password" htmlFor="password">
            <input
              id="password"
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
          <button className="btn-primary w-full" disabled={busy}>
            {busy && <Spinner />} Sign in
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-500">
          No account?{" "}
          <Link to="/register" className="font-medium text-brand-600 hover:text-brand-700">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
