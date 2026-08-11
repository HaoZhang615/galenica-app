import type { LucideIcon } from "lucide-react";
import { Card } from "./ui";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  icon?: LucideIcon;
  accent?: "primary" | "critical" | "warning" | "healthy" | "overstock";
}

const accentMap: Record<string, string> = {
  primary: "text-primary bg-primary/10",
  critical: "text-critical bg-critical/10",
  warning: "text-warning bg-warning/10",
  healthy: "text-healthy bg-healthy/10",
  overstock: "text-overstock bg-overstock/10",
};

export function KpiCard({ label, value, unit, sub, icon: Icon, accent = "primary" }: Props) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        {Icon && (
          <div className={cn("flex h-8 w-8 items-center justify-center rounded-md", accentMap[accent])}>
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="text-3xl font-semibold tracking-tight tabular-nums">{value}</span>
        {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
      </div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </Card>
  );
}
