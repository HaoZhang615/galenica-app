import {
  Activity,
  Bell,
  Map as MapIcon,
  MessageSquareText,
  Moon,
  Pill,
  Sun,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "@/lib/api";
import { useAsync, useTheme } from "@/lib/hooks";
import { Badge } from "./ui";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Overview", icon: Activity, end: true },
  { to: "/map", label: "Network map", icon: MapIcon },
  { to: "/alerts", label: "Alerts & reorders", icon: Bell },
  { to: "/assistant", label: "Ask your data", icon: MessageSquareText },
];

export default function Layout() {
  const { dark, toggle } = useTheme();
  const { data: who } = useAsync(() => api.whoami(), []);

  return (
    <div className="min-h-screen">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r bg-card px-3 py-5 md:flex">
        <div className="flex items-center gap-2 px-2 pb-6">
          <div className="brand-gradient flex h-9 w-9 items-center justify-center rounded-lg text-white">
            <Pill className="h-5 w-5" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">Galenica</div>
            <div className="text-xs text-muted-foreground">Demand Forecasting</div>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-2 text-[11px] text-muted-foreground">
          <div>Databricks App · Lakebase</div>
          <div className="mt-1">Model: {who?.serving_endpoint ?? "—"}</div>
        </div>
      </aside>

      {/* Main column */}
      <div className="md:pl-60">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b bg-background/80 px-5 backdrop-blur">
          <div className="flex items-center gap-2">
            <Badge variant={who?.mode === "live" ? "healthy" : "outline"}>
              {who?.mode === "live" ? "Live data" : "Demo data"}
            </Badge>
            <span className="hidden text-xs text-muted-foreground sm:inline">
              {who?.catalog}.{who?.schema}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-muted-foreground sm:inline">
              {who?.user ?? "…"}
            </span>
            <button
              onClick={toggle}
              className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-5 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
