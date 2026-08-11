export interface Kpis {
  forecast_demand_7d: number;
  critical_alerts: number;
  warning_alerts: number;
  overstock_alerts: number;
  pharmacies_at_risk: number;
  total_pharmacies: number;
  total_products: number;
  avg_days_cover: number | null;
  forecast_accuracy_pct: number;
}

export interface TrendPoint {
  date: string;
  actual: number | null;
  forecast: number | null;
}

export interface Pharmacy {
  pharmacy_id: string;
  name: string;
  banner: string;
  canton_code: string;
  canton_name: string;
  city: string;
  latitude: number;
  longitude: number;
  size_factor: number;
  critical_alerts: number;
  warning_alerts: number;
  overstock_alerts: number;
  risk_score: number;
}

export interface Overview {
  kpis: Kpis;
  national_trend: TrendPoint[];
  top_risk_pharmacies: Pharmacy[];
  data_source: string;
  generated_at: string;
}

export interface ProductRisk {
  product_id: string;
  product_name: string;
  category: string;
  is_rx: boolean;
  demand_7d: number;
  on_hand: number;
  days_cover: number;
  severity: string | null;
  recommended_qty: number;
}

export interface Annotation {
  id: number;
  pharmacy_id: string;
  product_id: string | null;
  note: string;
  author: string;
  created_at: string;
}

export interface PharmacyDetail {
  pharmacy: Pharmacy;
  products: ProductRisk[];
  annotations: Annotation[];
}

export interface ForecastPoint {
  day: number;
  date: string;
  p10: number;
  p50: number;
  p90: number;
}

export interface ActualPoint {
  date: string;
  units: number;
}

export interface ForecastResponse {
  pharmacy: Pharmacy;
  product: ProductRisk;
  actuals: ActualPoint[];
  forecast: ForecastPoint[];
  source: string;
}

export interface Alert {
  id: number;
  pharmacy_id: string;
  product_id: string;
  pharmacy_name?: string;
  product_name?: string;
  canton_code?: string;
  severity: string;
  demand_7d?: number;
  forecast_demand_7d?: number;
  on_hand: number;
  days_cover: number;
  status: string;
  acknowledged_by?: string | null;
}

export interface AlertsResponse {
  rows: Alert[];
  total: number;
  page: number;
  page_size: number;
}

export interface Reorder {
  id: number;
  pharmacy_id: string;
  product_id: string;
  pharmacy_name?: string;
  product_name?: string;
  recommended_qty: number;
  decided_qty: number | null;
  status: string;
  decided_by: string | null;
}

export interface WhoAmI {
  user: string;
  mode: string;
  catalog: string;
  schema: string;
  serving_endpoint: string;
}

export interface AssistantResponse {
  answer: string;
  sql: string;
  sources: string[];
  source: string;
  user: string;
  disclaimer: string;
}
