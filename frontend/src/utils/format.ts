const TZ = "Asia/Kolkata";

export function clockTime(iso: string | null | undefined, withSeconds = true): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-GB", {
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    ...(withSeconds ? { second: "2-digit" } : {}),
  });
}

export function agoText(iso: string | null | undefined, now: number): string {
  if (!iso) return "never";
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 5) return "just now";
  if (s < 90) return `${s} s ago`;
  const m = Math.round(s / 60);
  return m < 90 ? `${m} min ago` : `${Math.round(m / 60)} h ago`;
}

export function num(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number.isInteger(v) ? String(v) : v.toFixed(digits).replace(/\.0$/, "");
}

export function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const r = Math.round(v);
  return `${r > 0 ? "+" : ""}${r}%`;
}

export function withUnit(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined) return "—";
  if (unit === "%") return `${num(v)}%`;
  if (unit === "reports") return `${num(v, 0)}`;
  return `${num(v)} ${unit}`;
}
