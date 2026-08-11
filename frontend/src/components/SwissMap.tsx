import { useMemo, useState } from "react";
import type { Pharmacy } from "@/lib/types";
import { cn } from "@/lib/utils";

// Geographic bounds of Switzerland (approx), used for a simple equirectangular
// projection of pharmacy coordinates onto the SVG canvas.
const LON_MIN = 5.9, LON_MAX = 10.55;
const LAT_MIN = 45.8, LAT_MAX = 47.85;
const W = 820, H = 470, PAD = 24;

function project(lon: number, lat: number) {
  const x = PAD + ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * (W - 2 * PAD);
  const y = PAD + (1 - (lat - LAT_MIN) / (LAT_MAX - LAT_MIN)) * (H - 2 * PAD);
  return { x, y };
}

function riskLevel(p: Pharmacy): "critical" | "warning" | "overstock" | "healthy" {
  if (p.critical_alerts > 0) return "critical";
  if (p.warning_alerts > 0) return "warning";
  if (p.overstock_alerts > 0) return "overstock";
  return "healthy";
}

const FILL: Record<string, string> = {
  critical: "hsl(var(--critical))",
  warning: "hsl(var(--warning))",
  overstock: "hsl(var(--overstock))",
  healthy: "hsl(var(--healthy))",
};

export function SwissMap({
  pharmacies,
  onSelect,
}: {
  pharmacies: Pharmacy[];
  onSelect: (id: string) => void;
}) {
  const [hover, setHover] = useState<{ p: Pharmacy; x: number; y: number } | null>(null);

  // canton label positions = mean of member pharmacy coordinates
  const cantonLabels = useMemo(() => {
    const groups: Record<string, { lat: number; lon: number; n: number; code: string }> = {};
    for (const p of pharmacies) {
      const g = (groups[p.canton_code] ??= { lat: 0, lon: 0, n: 0, code: p.canton_code });
      g.lat += p.latitude;
      g.lon += p.longitude;
      g.n += 1;
    }
    return Object.values(groups)
      .filter((g) => g.n >= 6)
      .map((g) => ({ code: g.code, ...project(g.lon / g.n, g.lat / g.n) }));
  }, [pharmacies]);

  // render most-severe last so they sit on top
  const order = { healthy: 0, overstock: 1, warning: 2, critical: 3 } as const;
  const sorted = [...pharmacies].sort((a, b) => order[riskLevel(a)] - order[riskLevel(b)]);

  return (
    <div className="relative w-full overflow-hidden">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Pharmacy network map">
        <rect x={2} y={2} width={W - 4} height={H - 4} rx={16} className="fill-muted/40 stroke-border" />
        {cantonLabels.map((c) => (
          <text
            key={c.code}
            x={c.x}
            y={c.y}
            className="fill-muted-foreground"
            fontSize={13}
            fontWeight={600}
            textAnchor="middle"
            opacity={0.35}
          >
            {c.code}
          </text>
        ))}
        {sorted.map((p) => {
          const { x, y } = project(p.longitude, p.latitude);
          const lvl = riskLevel(p);
          const r = 2.6 + p.size_factor * 2.2;
          return (
            <circle
              key={p.pharmacy_id}
              cx={x}
              cy={y}
              r={r}
              fill={FILL[lvl]}
              fillOpacity={lvl === "healthy" ? 0.55 : 0.9}
              stroke="hsl(var(--card))"
              strokeWidth={0.6}
              className="cursor-pointer transition-transform hover:scale-150"
              onMouseEnter={() => setHover({ p, x, y })}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelect(p.pharmacy_id)}
            />
          );
        })}
      </svg>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border bg-card px-3 py-2 text-xs shadow-md"
          style={{
            left: `${(hover.x / W) * 100}%`,
            top: `${(hover.y / H) * 100}%`,
            transform: "translate(-50%, -120%)",
          }}
        >
          <div className="font-semibold">{hover.p.name}</div>
          <div className="text-muted-foreground">{hover.p.canton_name}</div>
          <div className="mt-1 flex gap-2">
            <span className="text-critical">{hover.p.critical_alerts} crit</span>
            <span className="text-warning">{hover.p.warning_alerts} warn</span>
            <span className="text-overstock">{hover.p.overstock_alerts} over</span>
          </div>
        </div>
      )}

      {/* legend */}
      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        {(["critical", "warning", "overstock", "healthy"] as const).map((k) => (
          <div key={k} className="flex items-center gap-1.5">
            <span className={cn("inline-block h-2.5 w-2.5 rounded-full")} style={{ background: FILL[k] }} />
            <span className="capitalize">{k}</span>
          </div>
        ))}
        <span className="ml-auto">Dot size ∝ pharmacy volume · click to drill in</span>
      </div>
    </div>
  );
}
