import { NavLink } from "react-router-dom";
import { Activity, Settings as SettingsIcon, User, Watch } from "lucide-react";
import clsx from "clsx";
import type { LucideIcon } from "lucide-react";

const TABS: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/", label: "Plans", icon: Activity },
  { to: "/garmin", label: "My Board", icon: Watch },
  { to: "/profile", label: "Profile", icon: User },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

/**
 * Thumb-reachable bottom navigation, shown only on phones (`sm:hidden`).
 * The desktop top nav in Layout takes over from the `sm` breakpoint up.
 */
export function BottomTabBar() {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 backdrop-blur sm:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      aria-label="Primary"
    >
      <div className="mx-auto flex max-w-md items-stretch justify-around">
        {TABS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex min-h-[44px] flex-1 flex-col items-center justify-center gap-0.5 px-2 py-2 text-[11px] font-medium transition-colors",
                isActive ? "text-brand-700" : "text-slate-500 hover:text-slate-800",
              )
            }
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
