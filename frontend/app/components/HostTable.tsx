"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import type { Asset } from "../lib/api";
import {
  STATUS_STYLE,
  missingSecurityHeaders,
  statusClass,
} from "../lib/format";

type Filter = "all" | "web" | "noweb" | "redirect" | "errors" | "new";
type SortKey = "hostname" | "status" | "ip";

type Props = {
  assets: Asset[];
  newHosts: Set<string>;
  changedHosts: Set<string>;
  activeHost: string | null;
  onActive: (host: string | null) => void;
  onVisibleChange: (visible: Asset[]) => void;
};

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "web", label: "Web service" },
  { id: "noweb", label: "No web service" },
  { id: "redirect", label: "Redirects" },
  { id: "errors", label: "Errors" },
  { id: "new", label: "New" },
];

const SOURCE_LABEL: Record<string, string> = {
  ct: "Certificates",
  bruteforce: "Wordlist",
  apex: "Domain",
};

function matches(a: Asset, f: Filter, isNew: boolean): boolean {
  const cls = statusClass(a.http_status);
  switch (f) {
    case "web": return cls !== "none";
    case "noweb": return cls === "none";
    case "redirect": return cls === "3xx";
    case "errors": return cls === "4xx" || cls === "5xx";
    case "new": return isNew;
    default: return true;
  }
}

export default function HostTable({
  assets,
  newHosts,
  changedHosts,
  activeHost,
  onActive,
  onVisibleChange,
}: Props) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("hostname");
  const [asc, setAsc] = useState(true);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = assets.filter((a) => {
      if (!matches(a, filter, newHosts.has(a.hostname))) return false;
      if (!q) return true;
      return [a.hostname, a.title ?? "", a.ip_address ?? "", ...a.tech_stack, ...a.cname]
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
    const dir = asc ? 1 : -1;
    const key = (a: Asset): string | number =>
      sortKey === "status" ? (a.http_status ?? 0) : sortKey === "ip" ? (a.ip_address ?? "") : a.hostname;
    list.sort((a, b) => (key(a) < key(b) ? -dir : key(a) > key(b) ? dir : 0));
    return list;
  }, [assets, query, filter, sortKey, asc, newHosts]);

  // Let the parent export exactly what is on screen.
  useEffect(() => {
    onVisibleChange(rows);
  }, [rows, onVisibleChange]);

  function sortBy(k: SortKey) {
    if (k === sortKey) setAsc(!asc);
    else { setSortKey(k); setAsc(true); }
  }

  const arrow = (k: SortKey) => (k === sortKey ? (asc ? " ▲" : " ▼") : "");
  const th = "px-3 py-2.5 text-left font-medium text-mist";

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search hostnames, titles, IPs, technologies"
          aria-label="Search hosts"
          className="w-full rounded-lg border border-reef bg-trench px-3.5 py-2 text-sm placeholder:text-mist/60 sm:w-80"
        />
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter hosts">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              aria-pressed={filter === f.id}
              className={`rounded-full border px-3 py-1 text-sm ${
                filter === f.id
                  ? "border-sonar bg-sonar/15 text-sonar"
                  : "border-reef text-mist hover:text-foam"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <p className="mt-3 text-sm text-mist" aria-live="polite">
        Showing {rows.length} of {assets.length} hosts
      </p>

      <div className="mt-2 overflow-x-auto rounded-xl border border-reef">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead className="bg-trench">
            <tr>
              <th className={th} aria-sort={sortKey === "hostname" ? (asc ? "ascending" : "descending") : "none"}>
                <button onClick={() => sortBy("hostname")}>Host{arrow("hostname")}</button>
              </th>
              <th className={th} aria-sort={sortKey === "status" ? (asc ? "ascending" : "descending") : "none"}>
                <button onClick={() => sortBy("status")}>Status{arrow("status")}</button>
              </th>
              <th className={th}>Page title</th>
              <th className={th} aria-sort={sortKey === "ip" ? (asc ? "ascending" : "descending") : "none"}>
                <button onClick={() => sortBy("ip")}>IP{arrow("ip")}</button>
              </th>
              <th className={th}>Technologies</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center text-mist">
                  No hosts match. Clear the search or pick another filter.
                </td>
              </tr>
            )}
            {rows.map((a) => {
              const cls = statusClass(a.http_status);
              const st = STATUS_STYLE[cls];
              const open = activeHost === a.hostname;
              const missing = missingSecurityHeaders(a);
              return (
                <Fragment key={a.hostname}>
                  <tr
                    onClick={() => onActive(open ? null : a.hostname)}
                    className={`cursor-pointer border-t border-reef/60 ${
                      open ? "bg-trench-2" : "hover:bg-trench/70"
                    }`}
                  >
                    <td className="px-3 py-2.5">
                      <button
                        aria-expanded={open}
                        className="text-left font-mono text-foam"
                        onClick={(e) => { e.stopPropagation(); onActive(open ? null : a.hostname); }}
                      >
                        {a.hostname}
                      </button>
                      {newHosts.has(a.hostname) && (
                        <span className="ml-2 rounded-md bg-kelp/15 px-1.5 py-0.5 text-xs text-kelp">new</span>
                      )}
                      {changedHosts.has(a.hostname) && (
                        <span className="ml-2 rounded-md bg-flare/15 px-1.5 py-0.5 text-xs text-flare">changed</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${st.bg} ${st.text}`}>
                        {a.http_status ?? "No web"}
                      </span>
                    </td>
                    <td className="max-w-[260px] truncate px-3 py-2.5 text-mist" title={a.title ?? undefined}>
                      {a.title ?? "-"}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-mist">{a.ip_address ?? "-"}</td>
                    <td className="px-3 py-2.5 text-mist">{a.tech_stack.join(", ") || "-"}</td>
                  </tr>
                  {open && (
                    <tr className="bg-trench-2">
                      <td colSpan={5} className="px-4 pb-5 pt-1">
                        <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
                          <Detail label="IP addresses" mono value={a.ips.join(", ") || "None"} />
                          <Detail label="CNAME chain" mono value={a.cname.join(" > ") || "None"} />
                          <Detail
                            label="Redirects to"
                            mono
                            value={a.redirect_url ?? "No redirect"}
                          />
                          <Detail
                            label="Found by"
                            value={a.sources.map((s) => SOURCE_LABEL[s] ?? s).join(", ") || "Unknown"}
                          />
                          {missing.length > 0 && (
                            <Detail label="Missing security headers" value={missing.join(", ")} warn />
                          )}
                        </dl>
                        {Object.keys(a.headers).length > 0 && (
                          <div className="mt-4">
                            <p className="text-sm font-medium">Response headers</p>
                            <pre className="mt-1.5 overflow-x-auto rounded-lg bg-sea p-3 font-mono text-xs leading-relaxed text-mist">
                              {Object.entries(a.headers).map(([k, v]) => `${k}: ${v}`).join("\n")}
                            </pre>
                          </div>
                        )}
                        <button
                          className="mt-3 text-sm text-sonar underline underline-offset-4"
                          onClick={() => navigator.clipboard?.writeText(a.hostname)}
                        >
                          Copy hostname
                        </button>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Detail({
  label,
  value,
  mono,
  warn,
}: {
  label: string;
  value: string;
  mono?: boolean;
  warn?: boolean;
}) {
  return (
    <div>
      <dt className="text-mist">{label}</dt>
      <dd className={`mt-0.5 break-all ${mono ? "font-mono text-xs" : ""} ${warn ? "text-flare" : "text-foam"}`}>
        {value}
      </dd>
    </div>
  );
}
