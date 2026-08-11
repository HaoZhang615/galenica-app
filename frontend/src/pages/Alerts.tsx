import { Check, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  LoadingState,
  severityVariant,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { fmtNum } from "@/lib/utils";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 15;

export default function Alerts() {
  const [tab, setTab] = useState<"alerts" | "reorders">("alerts");
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Alerts & reorder decisions</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Acknowledgements and reorder decisions are written back to Lakebase
        </p>
      </div>
      <div className="flex gap-1 rounded-lg border bg-card p-1 text-sm w-fit">
        {(["alerts", "reorders"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "rounded-md px-4 py-1.5 font-medium capitalize transition-colors",
              tab === t ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "alerts" ? <AlertsTab /> : <ReordersTab />}
    </div>
  );
}

function AlertsTab() {
  const [severity, setSeverity] = useState<string>("");
  const [status, setStatus] = useState<string>("open");
  const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useAsync(
    () => api.alerts({ severity: severity || undefined, status, page, page_size: PAGE_SIZE }),
    [severity, status, page]
  );

  const ack = async (id: number) => {
    await api.acknowledgeAlert(id);
    reload();
  };

  const pages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <Card>
      <CardContent className="pt-5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Select value={severity} onChange={(v) => { setSeverity(v); setPage(1); }}
            options={[["", "All severities"], ["critical", "Critical"], ["warning", "Warning"], ["overstock", "Overstock"]]} />
          <Select value={status} onChange={(v) => { setStatus(v); setPage(1); }}
            options={[["open", "Open"], ["acknowledged", "Acknowledged"], ["all", "All"]]} />
          {data && <span className="ml-auto text-xs text-muted-foreground">{fmtNum(data.total, 0)} alerts</span>}
        </div>

        {loading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : !data || data.rows.length === 0 ? (
          <EmptyState title="No alerts match" hint="Try a different filter." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-2 py-2">Severity</th>
                    <th className="px-2 py-2">Pharmacy</th>
                    <th className="px-2 py-2">Product</th>
                    <th className="px-2 py-2 text-right">On hand</th>
                    <th className="px-2 py-2 text-right">Days cover</th>
                    <th className="px-2 py-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((a) => (
                    <tr key={a.id} className="border-b last:border-0 hover:bg-muted/50">
                      <td className="px-2 py-2">
                        <Badge variant={severityVariant(a.severity) as never}>{a.severity}</Badge>
                      </td>
                      <td className="px-2 py-2">
                        <Link to={`/pharmacy/${a.pharmacy_id}`} className="hover:text-primary hover:underline">
                          {a.pharmacy_name ?? a.pharmacy_id}
                        </Link>
                        {a.canton_code && <span className="ml-1 text-xs text-muted-foreground">{a.canton_code}</span>}
                      </td>
                      <td className="px-2 py-2">{a.product_name ?? a.product_id}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{fmtNum(a.on_hand, 0)}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{fmtNum(a.days_cover)}</td>
                      <td className="px-2 py-2 text-right">
                        {a.status === "acknowledged" ? (
                          <span className="text-xs text-muted-foreground">✓ {a.acknowledged_by}</span>
                        ) : (
                          <Button size="sm" variant="outline" onClick={() => ack(a.id)}>
                            <Check className="h-3.5 w-3.5" /> Ack
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={page} pages={pages} onPage={setPage} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ReordersTab() {
  const { data, loading, error, reload } = useAsync(() => api.reorders("pending"), []);
  const decide = async (id: number, qty: number, status: string) => {
    await api.decideReorder(id, qty, status);
    reload();
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data || data.rows.length === 0)
    return <Card><CardContent className="pt-5"><EmptyState title="No pending reorders" /></CardContent></Card>;

  return (
    <Card>
      <CardContent className="overflow-x-auto pt-5">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-2 py-2">Pharmacy</th>
              <th className="px-2 py-2">Product</th>
              <th className="px-2 py-2 text-right">Recommended</th>
              <th className="px-2 py-2 text-right">Decision</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.slice(0, 40).map((r) => (
              <ReorderRow key={r.id} r={r} onDecide={decide} />
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function ReorderRow({
  r,
  onDecide,
}: {
  r: { id: number; pharmacy_name?: string; pharmacy_id: string; product_name?: string; product_id: string; recommended_qty: number };
  onDecide: (id: number, qty: number, status: string) => void;
}) {
  const [qty, setQty] = useState(r.recommended_qty);
  return (
    <tr className="border-b last:border-0 hover:bg-muted/50">
      <td className="px-2 py-2">
        <Link to={`/pharmacy/${r.pharmacy_id}`} className="hover:text-primary hover:underline">
          {r.pharmacy_name ?? r.pharmacy_id}
        </Link>
      </td>
      <td className="px-2 py-2">{r.product_name ?? r.product_id}</td>
      <td className="px-2 py-2 text-right tabular-nums">{r.recommended_qty}</td>
      <td className="px-2 py-2">
        <div className="flex items-center justify-end gap-2">
          <input
            type="number"
            value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
            className="w-20 rounded-md border bg-background px-2 py-1 text-right text-sm outline-none focus:ring-2 focus:ring-ring"
          />
          <Button size="sm" variant="success" onClick={() => onDecide(r.id, qty, "approved")}>
            <Check className="h-3.5 w-3.5" /> Approve
          </Button>
          <Button size="sm" variant="outline" onClick={() => onDecide(r.id, 0, "rejected")}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </td>
    </tr>
  );
}

function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  return (
    <div className="mt-4 flex items-center justify-between text-sm">
      <span className="text-xs text-muted-foreground">Page {page} of {pages}</span>
      <div className="flex gap-1">
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
    >
      {options.map(([v, l]) => (
        <option key={v} value={v}>{l}</option>
      ))}
    </select>
  );
}
