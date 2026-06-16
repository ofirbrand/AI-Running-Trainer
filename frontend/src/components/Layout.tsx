import { NavLink, useNavigate } from "react-router-dom";
import { Activity, LogOut, Settings as SettingsIcon, User, Watch } from "lucide-react";
import clsx from "clsx";
import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";

function NavItem({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        clsx(
          "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-brand-50 text-brand-700"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
        )
      }
    >
      {children}
    </NavLink>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2 font-bold text-slate-900">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Activity className="h-5 w-5" />
            </span>
            AI Running Coach
          </NavLink>

          {user && (
            <nav className="flex items-center gap-1">
              <NavItem to="/">Dashboard</NavItem>
              <NavItem to="/garmin">
                <span className="flex items-center gap-1.5">
                  <Watch className="h-4 w-4" /> My Garmin
                </span>
              </NavItem>
              <NavItem to="/profile">
                <span className="flex items-center gap-1.5">
                  <User className="h-4 w-4" /> Profile
                </span>
              </NavItem>
              <NavItem to="/settings">
                <span className="flex items-center gap-1.5">
                  <SettingsIcon className="h-4 w-4" /> Settings
                </span>
              </NavItem>
              <button
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
                className="ml-2 inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600"
              >
                <LogOut className="h-4 w-4" /> Log out
              </button>
            </nav>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
