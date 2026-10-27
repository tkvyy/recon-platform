"use client";

import { useMemo } from "react";
import type { ScanSummary } from "../lib/api";
import { formatWhen } from "../lib/format";

type Props = {
  email: string;
  scans: ScanSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (scan: ScanSummary) => void;
  onLogout: () => void;
};

const DOT: Record<string, string> = {
  COMPLETED: "bg-kelp",
  FAILED: "bg-coral",
  RUNNING: "bg-flare",
  QUEUED: "bg-flare",
  CANCELLED: "bg-mist",
};

export default function Sidebar({
  email,
  scans,
  selectedId,
  onSelect,
  onDelete,
  onLogout,
}: Props) {
  // Scans arrive newest first; keep that order inside each target.
  const groups = useMemo(() => {
    const map = new Map<string, ScanSummary[]>();
    for (const s of scans) {
      map.set(s.target_domain, [...(map.get(s.target_domain) ?? []), s]);
    }
    return [...map.entries()];
  }, [scans]);

  return (
    <aside className="flex flex-col border-b border-reef bg-trench lg:h-full lg:w-[300px] lg:border-b-0 lg:border-r">
      <div className="px-5 pb-4 pt-6">
        <p className="text-lg font-semibold tracking-tight">Attack Surface Recon</p>
        <p className="mt-0.5 truncate text-sm text-mist">{email}</p>
      </div>

      <nav aria-label="Scan history" className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {groups.length === 0 && (
          <p className="px-2 py-4 text-sm text-mist">
            No scans yet. Enter a domain you own and start your first scan.
          </p>
        )}
        {groups.map(([target, items]) => (
          <section key={target} className="mt-3">
            <h2 className="truncate px-2 font-mono text-sm font-medium text-foam">
              {target}
            </h2>
            <ul className="mt-1">
              {items.map((s) => {
                const active = s.job_id === selectedId;
                return (
                  <li key={s.job_id} className="group relative">
                    <button
                      onClick={() => onSelect(s.job_id)}
                      aria-current={active ? "true" : undefined}
                      className={`flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left text-sm ${
                        active ? "bg-trench-2 text-foam" : "text-mist hover:bg-trench-2/60"
                      }`}
                    >
                      <span
                        className={`h-2 w-2 shrink-0 rounded-full ${DOT[s.status] ?? "bg-mist"}`}
                        title={s.status.toLowerCase()}
                      />
                      <span className="flex-1">{formatWhen(s.created_at)}</span>
                      <span className="pr-6 tabular-nums">{s.live_count}</span>
                    </button>
                    <button
                      onClick={() => onDelete(s)}
                      aria-label={`Delete scan of ${target} from ${formatWhen(s.created_at)}`}
                      className="absolute right-1.5 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded text-mist hover:bg-coral/15 hover:text-coral lg:hidden lg:focus-visible:flex lg:group-hover:flex"
                    >
                      ×
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </nav>

      <div className="border-t border-reef px-5 py-3">
        <button onClick={onLogout} className="text-sm text-mist underline underline-offset-4 hover:text-foam">
          Log out
        </button>
      </div>
    </aside>
  );
}
