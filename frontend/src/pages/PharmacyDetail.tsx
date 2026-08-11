import { ArrowLeft, MessageSquarePlus, Package } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ForecastChart } from "@/components/ForecastChart";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  LoadingState,
  severityVariant,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { fmtNum } from "@/lib/utils";

export default function PharmacyDetail() {
  const { id = "" } = useParams();
  const detail = useAsync(() => api.pharmacy(id), [id]);
  const [selected, setSelected] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  // default to the most at-risk product once detail loads
  useEffect(() => {
    if (detail.data && !selected && detail.data.products.length) {
      const risky = detail.data.products.find((p) => p.severity) ?? detail.data.products[0];
      setSelected(risky.product_id);
    }
  }, [detail.data, selected]);

  const forecast = useAsync(
    () => (selected ? api.forecast(id, selected, 28, 90) : Promise.resolve(null as never)),
    [id, selected]
  );

  if (detail.loading) return <LoadingState />;
  if (detail.error || !detail.data)
    return <ErrorState error={detail.error ?? "Not found"} onRetry={detail.reload} />;

  const { pharmacy, products, annotations } = detail.data;
  const selectedProduct = products.find((p) => p.product_id === selected);

  const submitNote = async () => {
    if (!note.trim()) return;
    setSaving(true);
    try {
      await api.addAnnotation(id, note.trim(), selected ?? undefined);
      setNote("");
      detail.reload();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <Link to="/map" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back to network
      </Link>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{pharmacy.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {pharmacy.canton_name} · {pharmacy.banner} · {pharmacy.pharmacy_id}
          </p>
        </div>
        <div className="flex gap-2">
          {pharmacy.critical_alerts > 0 && <Badge variant="critical">{pharmacy.critical_alerts} critical</Badge>}
          {pharmacy.warning_alerts > 0 && <Badge variant="warning">{pharmacy.warning_alerts} warning</Badge>}
          {pharmacy.overstock_alerts > 0 && <Badge variant="overstock">{pharmacy.overstock_alerts} overstock</Badge>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Product list */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Products</CardTitle>
            <p className="text-xs text-muted-foreground">Sorted by risk · click to view forecast</p>
          </CardHeader>
          <CardContent className="max-h-[520px] space-y-1 overflow-y-auto">
            {products.map((p) => (
              <button
                key={p.product_id}
                onClick={() => setSelected(p.product_id)}
                className={`flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm hover:bg-muted ${
                  selected === p.product_id ? "bg-muted" : ""
                }`}
              >
                <div className="min-w-0">
                  <div className="truncate font-medium">{p.product_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.category} · cover {fmtNum(p.days_cover)}d
                  </div>
                </div>
                {p.severity && (
                  <Badge variant={severityVariant(p.severity) as never}>{p.severity}</Badge>
                )}
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Forecast + recommendation */}
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>
                {selectedProduct ? selectedProduct.product_name : "Forecast"}
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                90 days actual → 28 days forecast with 80% interval (p10–p90)
                {forecast.data?.source ? ` · source: ${forecast.data.source}` : ""}
              </p>
            </CardHeader>
            <CardContent>
              {forecast.loading && <LoadingState />}
              {forecast.error && <ErrorState error={forecast.error} onRetry={forecast.reload} />}
              {forecast.data && (
                <ForecastChart actuals={forecast.data.actuals} forecast={forecast.data.forecast} />
              )}
            </CardContent>
          </Card>

          {selectedProduct && (
            <Card>
              <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-5">
                <div className="flex items-center gap-6 text-sm">
                  <Metric label="On hand" value={`${fmtNum(selectedProduct.on_hand, 0)}`} />
                  <Metric label="7-day demand" value={fmtNum(selectedProduct.demand_7d)} />
                  <Metric label="Days cover" value={fmtNum(selectedProduct.days_cover)} />
                </div>
                {selectedProduct.recommended_qty > 0 ? (
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground">Recommended reorder</div>
                      <div className="text-lg font-semibold text-primary">
                        <Package className="mr-1 inline h-4 w-4" />
                        {fmtNum(selectedProduct.recommended_qty, 0)} units
                      </div>
                    </div>
                  </div>
                ) : (
                  <Badge variant="healthy">Stock healthy</Badge>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Annotations (Lakebase write-back) */}
      <Card>
        <CardHeader>
          <CardTitle>Notes</CardTitle>
          <p className="text-xs text-muted-foreground">Saved to Lakebase · shared across the team</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitNote()}
              placeholder="Add a note for this pharmacy…"
              className="flex-1 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <Button onClick={submitNote} disabled={saving || !note.trim()}>
              <MessageSquarePlus className="h-4 w-4" /> Add
            </Button>
          </div>
          {annotations.length === 0 ? (
            <EmptyState title="No notes yet" hint="Notes you add are persisted in Lakebase." />
          ) : (
            <ul className="space-y-2">
              {annotations.map((a) => (
                <li key={a.id} className="rounded-md border px-3 py-2 text-sm">
                  <div>{a.note}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {a.author} · {new Date(a.created_at).toLocaleString("de-CH")}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}
