import { useNavigate } from "react-router-dom";
import { GarminConnect } from "../components/GarminConnect";

export function OnboardingGarminPage() {
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Connect Garmin</h1>
      <p className="mb-6 text-sm text-slate-500">
        Link your Garmin account so the coach can track your activities, health, and fitness
        metrics. You can do this now or skip and connect later from your profile — but a plan needs
        your data to be accurate.
      </p>
      <div className="card p-6">
        <GarminConnect onConnected={() => navigate("/")} />
      </div>
      <button className="btn-ghost mt-4 w-full" onClick={() => navigate("/")}>
        Skip for now
      </button>
    </div>
  );
}
