import type {
  AlertsResponse,
  AssistantResponse,
  ForecastResponse,
  Overview,
  Pharmacy,
  PharmacyDetail,
  Reorder,
  WhoAmI,
} from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  whoami: () => get<WhoAmI>("/api/whoami"),
  overview: () => get<Overview>("/api/overview"),
  pharmacies: () => get<{ rows: Pharmacy[] }>("/api/pharmacies"),
  pharmacy: (id: string) => get<PharmacyDetail>(`/api/pharmacies/${id}`),
  forecast: (pharmacyId: string, productId: string, horizon = 28, historyDays = 90) =>
    get<ForecastResponse>(
      `/api/forecast?pharmacy_id=${pharmacyId}&product_id=${productId}&horizon=${horizon}&history_days=${historyDays}`
    ),
  alerts: (params: { status?: string; severity?: string; page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params.status) q.set("status", params.status);
    if (params.severity) q.set("severity", params.severity);
    q.set("page", String(params.page ?? 1));
    q.set("page_size", String(params.page_size ?? 25));
    return get<AlertsResponse>(`/api/alerts?${q.toString()}`);
  },
  acknowledgeAlert: (id: number) => post<unknown>(`/api/alerts/${id}/acknowledge`),
  reorders: (status = "pending") => get<{ rows: Reorder[] }>(`/api/reorders?status=${status}`),
  decideReorder: (id: number, decided_qty: number, status: string) =>
    post<Reorder>(`/api/reorders/${id}/decide`, { decided_qty, status }),
  addAnnotation: (pharmacyId: string, note: string, product_id?: string) =>
    post<unknown>(`/api/pharmacies/${pharmacyId}/annotations`, { note, product_id }),
  assistant: (question: string) => post<AssistantResponse>("/api/assistant", { question }),
};
