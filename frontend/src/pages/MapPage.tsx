import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { SwissMap } from "@/components/SwissMap";
import { Card, CardContent, CardHeader, CardTitle, ErrorState, LoadingState } from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { fmtInt } from "@/lib/utils";

export default function MapPage() {
  const { data, loading, error, reload } = useAsync(() => api.pharmacies(), []);
  const navigate = useNavigate();

  const cantonRollup = useMemo(() => {
    if (!data) return [];
    const g: Record<string, { code: string; name: string; crit: number; warn: number; n: number }> = {};
    for (const p of data.rows) {
      const row = (g[p.canton_code] ??= {
        code: p.canton_code,
        name: p.canton_name,
        crit: 0,
        warn: 0,
        n: 0,
      });
      row.crit += p.critical_alerts;
      row.warn += p.warning_alerts;
      row.n += 1;
    }
    return Object.values(g).sort((a, b) => b.crit - a.crit);
  }, [data]);

  if (loading) return <LoadingState />;
  if (error || !data) return <ErrorState error={error ?? "No data"} onRetry={reload} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Pharmacy network — stockout risk</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {fmtInt(data.rows.length)} pharmacies across Switzerland, coloured by highest active alert
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardContent className="pt-5">
            <SwissMap pharmacies={data.rows} onSelect={(id) => navigate(`/pharmacy/${id}`)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>By canton</CardTitle>
            <p className="text-xs text-muted-foreground">Critical alerts, descending</p>
          </CardHeader>
          <CardContent>
            <div className="max-h-[430px] space-y-1 overflow-y-auto pr-1">
              {cantonRollup.map((c) => (
                <div key={c.code} className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm">
                  <div>
                    <span className="font-medium">{c.code}</span>
                    <span className="ml-2 text-xs text-muted-foreground">{c.n} sites</span>
                  </div>
                  <div className="flex gap-3 text-xs tabular-nums">
                    <span className="text-critical">{c.crit}</span>
                    <span className="text-warning">{c.warn}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
