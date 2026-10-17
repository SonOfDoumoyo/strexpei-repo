const nairaWhole = new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 });
const nairaExact = new Intl.NumberFormat("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** ₦1,250 — shows kobo only when there are kobo. */
export function naira(kobo: number | null | undefined, opts: { exact?: boolean } = {}): string {
  const value = Number(kobo ?? 0) / 100;
  const sign = value < 0 ? "−" : "";
  const abs = Math.abs(value);
  const showKobo = opts.exact || !Number.isInteger(Math.round(abs * 100) / 100);
  return `${sign}₦${showKobo ? nairaExact.format(abs) : nairaWhole.format(abs)}`;
}

/** ₦8.4M / ₦240K for tight spaces and axes. */
export function nairaCompact(kobo: number): string {
  const value = kobo / 100;
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `₦${trim(value / 1_000_000_000)}B`;
  if (abs >= 1_000_000) return `₦${trim(value / 1_000_000)}M`;
  if (abs >= 1_000) return `₦${trim(value / 1_000)}K`;
  return `₦${Math.round(value)}`;
}

function trim(n: number): string {
  return n.toFixed(n >= 100 ? 0 : 1).replace(/\.0$/, "");
}

/** Parses "250,000.50" (naira) into kobo. Returns null when invalid. */
export function parseNaira(input: string): number | null {
  const clean = input.replace(/[₦,\s]/g, "");
  if (!clean) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
  const [whole, frac = ""] = clean.split(".");
  return Number(whole) * 100 + Number((frac + "00").slice(0, 2));
}

/** Formats a kobo amount for an editable naira input. */
export function toNairaInput(kobo: number | null | undefined): string {
  if (kobo === null || kobo === undefined) return "";
  const value = kobo / 100;
  return Number.isInteger(value) ? nairaWhole.format(value) : nairaExact.format(value);
}

/** Live-format digits as the user types: "250000" → "250,000". */
export function formatTypedNaira(raw: string): string {
  const clean = raw.replace(/[^\d.]/g, "");
  const [whole, ...rest] = clean.split(".");
  const frac = rest.join("").slice(0, 2);
  const formatted = whole ? nairaWhole.format(Number(whole)) : "";
  return clean.includes(".") ? `${formatted || "0"}.${frac}` : formatted;
}

const dateFmt = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const longDate = new Intl.DateTimeFormat("en-NG", { weekday: "long", day: "numeric", month: "long" });

export const date = (iso?: string | null) => (iso ? dateFmt.format(new Date(iso)) : "—");
export const dateTime = (iso?: string | null) => (iso ? dateTimeFmt.format(new Date(iso)) : "—");
export const dayLong = (iso?: string | null) => (iso ? longDate.format(new Date(iso)) : "—");

export function relative(iso?: string | null): string {
  if (!iso) return "—";
  const diff = (new Date(iso).getTime() - Date.now()) / 1000;
  const abs = Math.abs(diff);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (abs < 60) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), "day");
  return date(iso);
}

export function daysUntil(iso?: string | null): number | null {
  if (!iso) return null;
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

export const ordinal = (n: number) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

export const plural = (n: number, one: string, many = `${one}s`) => `${n.toLocaleString("en-NG")} ${n === 1 ? one : many}`;

export function initials(name?: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

export function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-NG", { month: "short" });
}

export function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}
