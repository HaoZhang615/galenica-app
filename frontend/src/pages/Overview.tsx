import { AlertTriangle, Boxes, Gauge, PackageCheck, TrendingUp } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { KpiCard } from "@/components/KpiCard";
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ErrorState,
  LoadingState,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { fmtDate, fmtInt } from "@/lib/utils";

export default function Overview() {
  const { data, loading, error, reload } = useAsync(() => api.overview(), []);
  const navigate = useNavigate();

  if (loading) return <LoadingState />;
  if (error || !data) return <ErrorState error={error ?? "No data"} onRetry={reload} />;

  const k = data.kpis;
  const freshness = new Date(data.generated_at).toLocaleString("de-CH");
  const css = (v: string) => `hsl(var(--${v}))`;
  const today = data.national_trend.find((t) => t.forecast !== null)?.date;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          {k.critical_alerts > 0
            ? `${fmtInt(k.critical_alerts)} critical stockouts need action across ${fmtInt(
                k.pharmacies_at_risk
              )} pharmacies`
            : "Network demand is on track"}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {fmtInt(k.total_pharmacies)} pharmacies · {fmtInt(k.total_products)} SKUs · forecast refreshed {freshness}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Forecast demand · 7d"
          value={fmtInt(k.forecast_demand_7d)}
          unit="units"
          sub="Sum of model p50, next 7 days"
          icon={TrendingUp}
          accent="primary"
        />
        <KpiCard
          label="Forecast accuracy"
          value={`${k.forecast_accuracy_pct}`}
          unit="%"
          sub="Rolling 30-day, 1 − MAPE"
          icon={Gauge}
          accent="healthy"
        />
        <KpiCard
          label="Critical stockouts"
          value={fmtInt(k.critical_alerts)}
          sub={`${fmtInt(k.warning_alerts)} warnings · ${fmtInt(k.pharmacies_at_risk)} sites affected`}
          icon={AlertTriangle}
          accent="critical"
        />
        <KpiCard
          label="Overstock signals"
          value={fmtInt(k.overstock_alerts)}
          sub={`Avg cover ${k.avg_days_cover ?? "—"} days`}
          icon={Boxes}
          accent="overstock"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>National demand — actual vs forecast</CardTitle>
            <p className="text-xs text-muted-foreground">
              Daily units across the network · last 30 days actual, next 28 days forecast
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={data.national_trend} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={fmtDate}
                  tick={{ fontSize: 11, fill: css("muted-foreground") }}
                  minTickGap={30}
                  stroke="hsl(var(--border))"
                />
                <YAxis
                  tick={{ fontSize: 11, fill: css("muted-foreground") }}
                  width={52}
                  stroke="hsl(var(--border))"
                  tickFormatter={(v) => fmtInt(v as number)}
                />
                <Tooltip
                  contentStyle={{
                    background: css("card"),
                    border: `1px solid ${css("border")}`,
                    borderRadius: 8,
                    fontSize: 12,
                    color: css("card-foreground"),
                  }}
                  labelFormatter={(l) => fmtDate(String(l))}
                  formatter={(v: unknown, n) => [fmtInt(v as number), n === "actual" ? "Actual" : "Forecast"]}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {today && <ReferenceLine x={today} stroke={css("muted-foreground")} strokeDasharray="4 4" />}
                <Area
                  type="monotone"
                  dataKey="forecast"
                  name="forecast"
                  stroke={css("forecast")}
                  fill={css("forecast")}
                  fillOpacity={0.12}
                  strokeWidth={2.5}
                  connectNulls
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="actual"
                  name="actual"
                  stroke={css("actual")}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Highest-risk pharmacies</CardTitle>
            <p className="text-xs text-muted-foreground">Ranked by weighted alert severity</p>
          </CardHeader>
          <CardContent className="space-y-1">
            {data.top_risk_pharmacies.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">No at-risk pharmacies 🎉</p>
            )}
            {data.top_risk_pharmacies.map((p) => (
              <button
                key={p.pharmacy_id}
                onClick={() => navigate(`/pharmacy/${p.pharmacy_id}`)}
                className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left hover:bg-muted"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{p.name}</div>
                  <div className="text-xs text-muted-foreground">{p.canton_name}</div>
                </div>
                <div className="flex shrink-0 gap-1">
                  {p.critical_alerts > 0 && <Badge variant="critical">{p.critical_alerts}</Badge>}
                  {p.warning_alerts > 0 && <Badge variant="warning">{p.warning_alerts}</Badge>}
                </div>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
