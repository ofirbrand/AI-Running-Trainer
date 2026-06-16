import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { PageLoader } from "./components/ui";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { OnboardingGarminPage } from "./pages/OnboardingGarminPage";
import { DashboardPage } from "./pages/DashboardPage";
import { MyGarminPage } from "./pages/MyGarminPage";
import { ProfilePage } from "./pages/ProfilePage";
import { CreatePlanPage } from "./pages/CreatePlanPage";
import { PlanOverviewPage } from "./pages/PlanOverviewPage";
import { TrackingPage } from "./pages/TrackingPage";
import { SettingsPage } from "./pages/SettingsPage";

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader label="Starting up…" />;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader label="Starting up…" />;
  if (user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicOnly>
            <LoginPage />
          </PublicOnly>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnly>
            <RegisterPage />
          </PublicOnly>
        }
      />
      <Route
        path="/connect"
        element={
          <Protected>
            <OnboardingGarminPage />
          </Protected>
        }
      />
      <Route
        path="/"
        element={
          <Protected>
            <DashboardPage />
          </Protected>
        }
      />
      <Route
        path="/garmin"
        element={
          <Protected>
            <MyGarminPage />
          </Protected>
        }
      />
      <Route
        path="/profile"
        element={
          <Protected>
            <ProfilePage />
          </Protected>
        }
      />
      <Route
        path="/settings"
        element={
          <Protected>
            <SettingsPage />
          </Protected>
        }
      />
      <Route
        path="/plans/new"
        element={
          <Protected>
            <CreatePlanPage />
          </Protected>
        }
      />
      <Route
        path="/plans/:id"
        element={
          <Protected>
            <PlanOverviewPage />
          </Protected>
        }
      />
      <Route
        path="/plans/:id/tracking"
        element={
          <Protected>
            <TrackingPage />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
