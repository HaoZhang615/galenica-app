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
import type { ActualPoint, ForecastPoint } from "@/lib/types";
import { fmtDate, fmtNum } from "@/lib/utils";

interface Row {
  date: string;
  actual?: number | null;
  p50?: number | null;
  band?: [number, number] | null;
}

export function ForecastChart({
  actuals,
  forecast,
}: {
  actuals: ActualPoint[];
  forecast: ForecastPoint[];
}) {
  const rows: Row[] = [
    ...actuals.map((a) => ({ date: a.date, actual: a.units })),
    ...forecast.map((f) => ({
      date: f.date,
      p50: f.p50,
      band: [f.p10, f.p90] as [number, number],
    })),
  ];
  const firstForecast = forecast[0]?.date;

  const css = (v: string) => `hsl(var(--${v}))`;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
        <defs>
          <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={css("forecast")} stopOpacity={0.22} />
            <stop offset="100%" stopColor={css("forecast")} stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={fmtDate}
          tick={{ fontSize: 11, fill: css("muted-foreground") }}
          minTickGap={28}
          stroke="hsl(var(--border))"
        />
        <YAxis
          tick={{ fontSize: 11, fill: css("muted-foreground") }}
          width={44}
          stroke="hsl(var(--border))"
          allowDecimals={false}
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
          formatter={(value: unknown, name) => {
            if (name === "p10–p90") {
              const b = value as [number, number];
              return [`${fmtNum(b[0])} – ${fmtNum(b[1])}`, "80% interval"];
            }
            return [fmtNum(value as number), name === "actual" ? "Actual" : "Forecast (p50)"];
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {firstForecast && (
          <ReferenceLine
            x={firstForecast}
            stroke={css("muted-foreground")}
            strokeDasharray="4 4"
            label={{ value: "today", position: "insideTopRight", fontSize: 10, fill: css("muted-foreground") }}
          />
        )}
        <Area
          type="monotone"
          dataKey="band"
          name="p10–p90"
          stroke="none"
          fill="url(#bandFill)"
          isAnimationActive={false}
          connectNulls
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
        <Line
          type="monotone"
          dataKey="p50"
          name="forecast"
          stroke={css("forecast")}
          strokeWidth={2.5}
          strokeDasharray="5 3"
          dot={false}
          connectNulls
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
