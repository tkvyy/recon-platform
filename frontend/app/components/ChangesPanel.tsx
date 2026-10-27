"use client";

import type { Diff } from "../lib/api";

const FIELD_LABEL: Record<string, string> = {
  ips: "IP addresses",
  cname: "CNAME",
  http_status: "Status code",
  title: "Page title",
  redirect_url: "Redirect",
  tech_stack: "Technologies",
};

function show(v: unknown): string {
  if (Array.isArray(v)) return v.length ? v.join(", ") : "none";
  if (v === null || v === undefined || v === "") return "none";
  return String(v);
}

type Props = {
  diff: Diff | null;
  loading: boolean;
  previousWhen: string | null; // formatted time of the scan we compare against
  error: string | null;
  onPick: (host: string) => void;
};

export default function ChangesPanel({ diff, loading, previousWhen, error, onPick }: Props) {
  if (loading) return <p className="text-mist">Comparing with the previous scan...</p>;
  if (error) return <p role="alert" className="rounded-lg bg-coral/15 px-3.5 py-2.5 text-coral">{error}</p>;
  if (!previousWhen || !diff) {
    return (
      <p className="max-w-xl text-mist">
        This is the first finished scan of this domain, so there is nothing to compare yet.
        Scan it again later and the new, removed and changed hosts will show up here.
      </p>
    );
  }
  const nothing = !diff.added.length && !diff.removed.length && !diff.changed.length;

  return (
    <div className="space-y-8">
      <p className="text-sm text-mist">Compared with the scan from {previousWhen}.</p>

      {nothing && (
        <p className="text-foam">
          Nothing changed. The same {diff.unchanged} hosts answered the same way.
        </p>
      )}

      {diff.added.length > 0 && (
        <Group title={`Added (${diff.added.length})`} tone="text-kelp">
          {diff.added.map((h) => (
            <li key={h}>
              <button className="font-mono text-foam hover:text-sonar" onClick={() => onPick(h)}>{h}</button>
            </li>
          ))}
        </Group>
      )}

      {diff.removed.length > 0 && (
        <Group title={`Gone (${diff.removed.length})`} tone="text-coral">
          {diff.removed.map((h) => (
            <li key={h} className="font-mono text-mist line-through decoration-coral/60">{h}</li>
          ))}
        </Group>
      )}

      {diff.changed.length > 0 && (
        <Group title={`Changed (${diff.changed.length})`} tone="text-flare">
          {diff.changed.map((c) => (
            <li key={c.hostname} className="rounded-lg border border-reef px-4 py-3">
              <button className="font-mono text-foam hover:text-sonar" onClick={() => onPick(c.hostname)}>
                {c.hostname}
              </button>
              <ul className="mt-2 space-y-1 text-sm">
                {Object.entries(c.changes).map(([field, v]) => (
                  <li key={field} className="flex flex-wrap gap-x-2">
                    <span className="text-mist">{FIELD_LABEL[field] ?? field}:</span>
                    <span className="text-coral/90 line-through decoration-coral/40">{show(v.old)}</span>
                    <span className="text-mist">to</span>
                    <span className="text-kelp">{show(v.new)}</span>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </Group>
      )}
    </div>
  );
}

function Group({ title, tone, children }: { title: string; tone: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className={`text-lg font-semibold ${tone}`}>{title}</h3>
      <ul className="mt-3 space-y-2">{children}</ul>
    </section>
  );
}
