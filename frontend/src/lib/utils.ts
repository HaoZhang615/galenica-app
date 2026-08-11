import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("de-CH").format(Math.round(n));
}

export function fmtNum(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("de-CH", { maximumFractionDigits: digits }).format(n);
}

export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("de-CH", { month: "short", day: "numeric" });
}
