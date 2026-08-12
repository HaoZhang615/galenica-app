import { useMemo, useState, useRef, useEffect } from "react";
import { geoMercator, geoPath } from "d3-geo";
import { select } from "d3-selection";
import { zoom as d3zoom, zoomIdentity, type ZoomBehavior, type D3ZoomEvent } from "d3-zoom";
import { Minus, Plus, Maximize2 } from "lucide-react";
import type { Pharmacy } from "@/lib/types";
import { cn } from "@/lib/utils";
import swissGeo from "@/assets/swiss-geo.json";

// Real Swiss geometry (country outline + 26 cantons + lakes), simplified and
// bundled. We fit a Mercator projection to the canton borders and reuse that
// same projection to place pharmacy dots, so points land exactly on the map.
const CANTONS = swissGeo.cantons as unknown as GeoJSON.FeatureCollection;
const COUNTRY = swissGeo.country as unknown as GeoJSON.FeatureCollection;
const LAKES = swissGeo.lakes as unknown as GeoJSON.FeatureCollection;

const W = 820, H = 520, PAD = 16;
const MAX_ZOOM = 12;

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
  const [t, setT] = useState({ k: 1, x: 0, y: 0 });

  const svgRef = useRef<SVGSVGElement | null>(null);
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  // True while a pan/zoom gesture is moving, so a drag doesn't fire a dot's click.
  const draggedRef = useRef(false);

  // Projection fitted to the country geometry; shared by borders + points.
  const projection = useMemo(
    () => geoMercator().fitExtent([[PAD, PAD], [W - PAD, H - PAD]], CANTONS),
    [],
  );
  const path = useMemo(() => geoPath(projection), [projection]);

  const project = (lon: number, lat: number) => {
    const p = projection([lon, lat]);
    return p ? { x: p[0], y: p[1] } : { x: -100, y: -100 };
  };

  const countryPath = useMemo(() => path(COUNTRY) ?? "", [path]);
  const cantonPaths = useMemo(() => CANTONS.features.map((f) => path(f) ?? ""), [path]);
  const lakePaths = useMemo(() => LAKES.features.map((f) => path(f) ?? ""), [path]);

  // Canton code labels = mean of member pharmacy coordinates, projected.
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pharmacies, projection]);

  // Attach d3-zoom (wheel/pinch zoom + drag pan), constrained to the map bounds.
  useEffect(() => {
    if (!svgRef.current) return;
    const sel = select(svgRef.current);
    const behavior = d3zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, MAX_ZOOM])
      .translateExtent([[0, 0], [W, H]])
      .on("start", () => {
        draggedRef.current = false;
      })
      .on("zoom", (e: D3ZoomEvent<SVGSVGElement, unknown>) => {
        // A pointer/touch move (not the +/- buttons) means the user is panning.
        if (e.sourceEvent && e.sourceEvent.type !== "wheel") draggedRef.current = true;
        setT({ k: e.transform.k, x: e.transform.x, y: e.transform.y });
      });
    zoomRef.current = behavior;
    sel.call(behavior);
    // Don't zoom on plain double-click (it competes with dot selection); keep wheel + drag.
    sel.on("dblclick.zoom", null);
    return () => {
      sel.on(".zoom", null);
    };
  }, []);

  const zoomBy = (factor: number) => {
    if (svgRef.current && zoomRef.current) {
      select(svgRef.current).call(zoomRef.current.scaleBy, factor);
    }
  };
  const resetZoom = () => {
    if (svgRef.current && zoomRef.current) {
      select(svgRef.current).call(zoomRef.current.transform, zoomIdentity);
    }
  };

  // render most-severe last so they sit on top
  const order = { healthy: 0, overstock: 1, warning: 2, critical: 3 } as const;
  const sorted = [...pharmacies].sort((a, b) => order[riskLevel(a)] - order[riskLevel(b)]);

  // Screen fraction of a projected point, accounting for the current zoom transform.
  const screenFrac = (x: number, y: number) => ({
    left: ((x * t.k + t.x) / W) * 100,
    top: ((y * t.k + t.y) / H) * 100,
  });

  return (
    <div className="relative w-full overflow-hidden">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-grab touch-none active:cursor-grabbing"
        role="img"
        aria-label="Pharmacy network map of Switzerland"
      >
        <g transform={`translate(${t.x},${t.y}) scale(${t.k})`}>
          {/* transparent surface so dragging anywhere pans the map */}
          <rect x={0} y={0} width={W} height={H} fill="transparent" pointerEvents="all" />

          {/* canton fills + borders */}
          {cantonPaths.map((d, i) => (
            <path
              key={i}
              d={d}
              className="fill-muted/50 stroke-border"
              strokeWidth={0.6}
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
            />
          ))}

          {/* lakes for geographic context */}
          {lakePaths.map((d, i) => (
            <path
              key={i}
              d={d}
              fill="#bae6fd"
              fillOpacity={0.55}
              stroke="#7dd3fc"
              strokeWidth={0.3}
              vectorEffect="non-scaling-stroke"
            />
          ))}

          {/* country outline on top */}
          <path
            d={countryPath}
            fill="none"
            className="stroke-muted-foreground/60"
            strokeWidth={1.4}
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />

          {/* canton code labels — counter-scaled so they stay legible when zoomed */}
          {cantonLabels.map((c) => (
            <text
              key={c.code}
              transform={`translate(${c.x},${c.y}) scale(${1 / t.k})`}
              className="fill-muted-foreground"
              fontSize={12}
              fontWeight={600}
              textAnchor="middle"
              opacity={0.4}
              pointerEvents="none"
            >
              {c.code}
            </text>
          ))}

          {/* pharmacy dots. Radius shrinks with zoom so dots don't bloat; each has a
              generous transparent hit area so it's easy to click. Hover grows the dot
              about its own centre (no CSS transform → no "jumping"). */}
          {sorted.map((p) => {
            const { x, y } = project(p.longitude, p.latitude);
            const lvl = riskLevel(p);
            const isHover = hover?.p.pharmacy_id === p.pharmacy_id;
            const base = 2.6 + p.size_factor * 2.2;
            const r = (isHover ? base * 1.5 : base) / t.k;
            const hit = Math.max(base + 4, 8) / t.k;
            return (
              <g
                key={p.pharmacy_id}
                className="cursor-pointer"
                onMouseEnter={() => setHover({ p, x, y })}
                onMouseLeave={() => setHover((h) => (h?.p.pharmacy_id === p.pharmacy_id ? null : h))}
                onClick={() => {
                  if (!draggedRef.current) onSelect(p.pharmacy_id);
                }}
              >
                <circle cx={x} cy={y} r={hit} fill="transparent" pointerEvents="all" />
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={FILL[lvl]}
                  fillOpacity={lvl === "healthy" ? 0.6 : 0.92}
                  stroke={isHover ? "hsl(var(--foreground))" : "hsl(var(--card))"}
                  strokeWidth={isHover ? 1.4 : 0.6}
                  vectorEffect="non-scaling-stroke"
                  pointerEvents="none"
                />
              </g>
            );
          })}
        </g>
      </svg>

      {/* zoom controls */}
      <div className="absolute right-2 top-2 flex flex-col gap-1">
        <button
          type="button"
          aria-label="Zoom in"
          onClick={() => zoomBy(1.6)}
          className="flex h-8 w-8 items-center justify-center rounded-md border bg-card text-muted-foreground shadow-sm hover:bg-muted"
        >
          <Plus className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Zoom out"
          onClick={() => zoomBy(1 / 1.6)}
          className="flex h-8 w-8 items-center justify-center rounded-md border bg-card text-muted-foreground shadow-sm hover:bg-muted"
        >
          <Minus className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Reset view"
          onClick={resetZoom}
          className="flex h-8 w-8 items-center justify-center rounded-md border bg-card text-muted-foreground shadow-sm hover:bg-muted"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border bg-card px-3 py-2 text-xs shadow-md"
          style={{
            left: `${screenFrac(hover.x, hover.y).left}%`,
            top: `${screenFrac(hover.x, hover.y).top}%`,
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
        <span className="ml-auto">Scroll to zoom · drag to pan · click a dot to drill in</span>
      </div>
    </div>
  );
}
