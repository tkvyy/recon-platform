import type { Asset } from "./api";

export type StatusClass = "2xx" | "3xx" | "4xx" | "5xx" | "none";

export function statusClass(code: number | null): StatusClass {
  if (code === null || code === undefined) return "none";
  if (code >= 200 && code < 300) return "2xx";
  if (code >= 300 && code < 400) return "3xx";
  if (code >= 400 && code < 500) return "4xx";
  if (code >= 500) return "5xx";
  return "none";
}

// Tailwind classes (text, background) and a raw colour for SVG, per status class.
export const STATUS_STYLE: Record<
  StatusClass,
  { text: string; bg: string; fill: string; label: string }
> = {
  "2xx": { text: "text-kelp", bg: "bg-kelp/15", fill: "#5be3a3", label: "Responding" },
  "3xx": { text: "text-sonar", bg: "bg-sonar/15", fill: "#3fd8e0", label: "Redirecting" },
  "4xx": { text: "text-flare", bg: "bg-flare/15", fill: "#ffb84d", label: "Client error" },
  "5xx": { text: "text-coral", bg: "bg-coral/15", fill: "#ff6b7a", label: "Server error" },
  none: { text: "text-mist", bg: "bg-mist/10", fill: "#4d7380", label: "No web service" },
};

/** Subdomain depth relative to the target: apex = 0, www.x.com = 1, a.b.x.com = 2. */
export function hostDepth(host: string, domain: string): number {
  if (host === domain) return 0;
  return Math.max(1, host.split(".").length - domain.split(".").length);
}

/** Stable 32-bit hash so a host keeps its place on the map between scans. */
export function hash32(text: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** The API sends naive UTC timestamps; mark them as UTC before parsing. */
export function parseUtc(iso: string | null): Date | null {
  if (!iso) return null;
  const hasZone = /(Z|[+-]\d\d:?\d\d)$/.test(iso);
  const d = new Date(hasZone ? iso : `${iso}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatWhen(iso: string | null): string {
  const d = parseUtc(iso);
  if (!d) return "unknown time";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const SECURITY_HEADERS: { key: string; label: string }[] = [
  { key: "strict-transport-security", label: "HSTS" },
  { key: "content-security-policy", label: "CSP" },
  { key: "x-frame-options", label: "X-Frame-Options" },
  { key: "x-content-type-options", label: "X-Content-Type-Options" },
];

export function missingSecurityHeaders(asset: Asset): string[] {
  if (asset.http_status === null) return [];
  const have = new Set(Object.keys(asset.headers ?? {}).map((k) => k.toLowerCase()));
  return SECURITY_HEADERS.filter((h) => !have.has(h.key)).map((h) => h.label);
}

// ---------------------------------------------------------------- export
function csvCell(value: unknown): string {
  let text = Array.isArray(value) ? value.join(" ") : String(value ?? "");
  // Stop spreadsheet apps from running a cell as a formula.
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

export function assetsToCsv(assets: Asset[]): string {
  const header = [
    "hostname", "ip_addresses", "cname", "status", "title",
    "redirect", "technologies", "found_by",
  ];
  const rows = assets.map((a) =>
    [
      a.hostname, a.ips, a.cname, a.http_status, a.title,
      a.redirect_url, a.tech_stack, a.sources,
    ]
      .map(csvCell)
      .join(","),
  );
  return [header.join(","), ...rows].join("\n");
}

export function downloadText(filename: string, text: string, mime: string) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
