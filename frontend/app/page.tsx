"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AuthPanel from "./components/AuthPanel";
import ChangesPanel from "./components/ChangesPanel";
import HostTable from "./components/HostTable";
import Sidebar from "./components/Sidebar";
import Sonar from "./components/Sonar";
import {
  ApiError,
  api,
  type Asset,
  type Diff,
  type Scan,
  type ScanSummary,
} from "./lib/api";
import { assetsToCsv, downloadText, formatWhen } from "./lib/format";

const TOKEN_KEY = "recon_token";
const EMAIL_KEY = "recon_email";
const SIDEBAR_KEY = "recon_sidebar";

type Tab = "hosts" | "changes";

const STATUS_PILL: Record<string, { text: string; cls: string }> = {
  COMPLETED: { text: "Finished", cls: "bg-kelp/15 text-kelp" },
  FAILED: { text: "Failed", cls: "bg-coral/15 text-coral" },
  RUNNING: { text: "Scanning", cls: "bg-flare/15 text-flare" },
  QUEUED: { text: "Waiting to start", cls: "bg-flare/15 text-flare" },
  CANCELLED: { text: "Stopped", cls: "bg-mist/15 text-mist" },
};

/** Accept "https://Example.com/path" and reduce it to "example.com". */
function cleanDomain(raw: string): string {
  return raw.trim().replace(/^https?:\/\//i, "").replace(/\/.*$/, "").toLowerCase();
}

export default function Home() {
  const [ready, setReady] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");

  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scan, setScan] = useState<Scan | null>(null);
  const [diff, setDiff] = useState<Diff | null>(null);
  const [diffErr, setDiffErr] = useState<{ id: string; message: string } | null>(null);

  const [tab, setTab] = useState<Tab>("hosts");
  const [activeHost, setActiveHost] = useState<string | null>(null);
  const [domain, setDomain] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const visibleRef = useRef<Asset[]>([]);
  const queuedPolls = useRef(0);
  const [stalledId, setStalledId] = useState<string | null>(null);

  // ------------------------------------------------------------ session
  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    setToken(null);
    setScans([]);
    setSelectedId(null);
    setScan(null);
    setDiff(null);
  }, []);

  const handleError = useCallback(
    (err: unknown, fallback = "Something went wrong.") => {
      if (err instanceof ApiError && err.status === 401) {
        clearSession();
        return;
      }
      setError(err instanceof ApiError ? err.message : fallback);
    },
    [clearSession],
  );

  useEffect(() => {
    const saved = localStorage.getItem(TOKEN_KEY);
    const check = saved
      ? api
          .me(saved)
          .then((u) => {
            setToken(saved);
            setEmail(u.email);
          })
          .catch(() => {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(EMAIL_KEY);
          })
      : Promise.resolve();
    check.finally(() => {
      setSidebarOpen(localStorage.getItem(SIDEBAR_KEY) !== "closed");
      setReady(true);
    });
  }, []);

  function toggleSidebar() {
    const next = !sidebarOpen;
    setSidebarOpen(next);
    localStorage.setItem(SIDEBAR_KEY, next ? "open" : "closed");
  }

  function onAuthed(newToken: string, userEmail: string) {
    localStorage.setItem(TOKEN_KEY, newToken);
    localStorage.setItem(EMAIL_KEY, userEmail);
    setToken(newToken);
    setEmail(userEmail);
    setError(null);
  }

  async function logout() {
    if (token) await api.logout(token).catch(() => undefined);
    clearSession();
  }

  // -------------------------------------------------------------- scans
  const refreshScans = useCallback(
    async (tk: string): Promise<ScanSummary[]> => {
      try {
        const list = await api.listScans(tk);
        setScans(list);
        return list;
      } catch (err) {
        handleError(err);
        return [];
      }
    },
    [handleError],
  );

  // Load history after login and open the newest scan.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api
      .listScans(token)
      .then((list) => {
        if (cancelled) return;
        setScans(list);
        if (list.length) setSelectedId((cur) => cur ?? list[0].job_id);
      })
      .catch((err) => {
        if (!cancelled) handleError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [token, handleError]);

  // Load the selected scan.
  useEffect(() => {
    if (!token || !selectedId) return;
    let cancelled = false;
    api
      .getScan(token, selectedId)
      .then((s) => {
        if (!cancelled) setScan(s);
      })
      .catch((err) => {
        if (!cancelled) handleError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [token, selectedId, handleError]);

  // Poll while the scan is running.
  const status = scan?.job_id === selectedId ? scan?.status : undefined;
  useEffect(() => {
    if (!token || !selectedId) return;
    if (status !== "QUEUED" && status !== "RUNNING") return;
    queuedPolls.current = 0;
    const timer = setInterval(async () => {
      try {
        const s = await api.getScan(token, selectedId);
        setScan(s);
        // Still waiting after ~15 seconds: probably no worker is running.
        queuedPolls.current = s.status === "QUEUED" ? queuedPolls.current + 1 : 0;
        if (queuedPolls.current >= 5) setStalledId(selectedId);
        if (s.status === "COMPLETED" || s.status === "FAILED") refreshScans(token);
      } catch (err) {
        handleError(err);
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [token, selectedId, status, refreshScans, handleError]);

  // The previous finished scan of the same target is the comparison baseline.
  const current = scan && scan.job_id === selectedId ? scan : null;
  const prevScan = useMemo(() => {
    if (!current) return null;
    const idx = scans.findIndex((s) => s.job_id === current.job_id);
    if (idx < 0) return null;
    return (
      scans
        .slice(idx + 1)
        .find((s) => s.target_domain === current.target_domain && s.status === "COMPLETED") ?? null
    );
  }, [scans, current]);
  const prevId = prevScan?.job_id ?? null;

  useEffect(() => {
    if (!token || !selectedId || !prevId || status !== "COMPLETED") return;
    let cancelled = false;
    api
      .diff(token, prevId, selectedId)
      .then((d) => {
        if (!cancelled) setDiff(d);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status !== 401) {
          setDiffErr({ id: selectedId, message: err.message });
        } else handleError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [token, selectedId, prevId, status, handleError]);

  const diffNow = diff && diff.new === selectedId ? diff : null;
  const diffError = diffErr && diffErr.id === selectedId ? diffErr.message : null;
  const diffLoading = status === "COMPLETED" && !!prevId && !diffNow && !diffError;
  const newHosts = useMemo(() => new Set(diffNow?.added ?? []), [diffNow]);
  const changedHosts = useMemo(
    () => new Set((diffNow?.changed ?? []).map((c) => c.hostname)),
    [diffNow],
  );

  async function startScan(target: string, force: boolean) {
    if (!token) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const r = await api.createScan(token, target, force);
      await refreshScans(token);
      setSelectedId(r.job_id);
      setTab("hosts");
      setActiveHost(null);
      if (r.reused) {
        setNotice(
          "You scanned this domain in the last 24 hours, so this is that scan. Use Scan again for fresh results.",
        );
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setError("That doesn't look like a domain. Try something like example.com.");
      } else handleError(err);
    } finally {
      setBusy(false);
    }
  }

  async function stopScan() {
    if (!token || !current) return;
    setError(null);
    try {
      await api.cancelScan(token, current.job_id);
      setScan(await api.getScan(token, current.job_id));
      await refreshScans(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // It finished a moment before the click; just show the real state.
        setScan(await api.getScan(token, current.job_id));
        await refreshScans(token);
      } else handleError(err);
    }
  }

  async function removeScan(s: ScanSummary) {
    if (!token) return;
    if (!window.confirm(`Delete the scan of ${s.target_domain} from ${formatWhen(s.created_at)}?`)) return;
    try {
      await api.deleteScan(token, s.job_id);
      if (s.job_id === selectedId) {
        setSelectedId(null);
        setScan(null);
      }
      await refreshScans(token);
    } catch (err) {
      handleError(err);
    }
  }

  function pickHost(host: string) {
    setTab("hosts");
    setActiveHost(host);
  }

  const onVisibleChange = useCallback((rows: Asset[]) => {
    visibleRef.current = rows;
  }, []);

  function exportView(kind: "csv" | "json") {
    if (!current) return;
    const base = `${current.target_domain}-${current.job_id.slice(0, 8)}`;
    const rows = visibleRef.current;
    if (kind === "csv") downloadText(`${base}.csv`, assetsToCsv(rows), "text/csv");
    else downloadText(`${base}.json`, JSON.stringify(rows, null, 2), "application/json");
  }

  // ------------------------------------------------------------- render
  if (!ready) return <div className="min-h-screen" />;
  if (!token) return <AuthPanel onAuthed={onAuthed} />;

  const target = cleanDomain(domain);
  const pill = current ? STATUS_PILL[current.status] ?? STATUS_PILL.QUEUED : null;
  const scanning = current?.status === "QUEUED" || current?.status === "RUNNING";
  const assets = current?.assets ?? [];
  const webCount = assets.filter((a) => a.http_status !== null).length;
  const dash = "-";
  const changeTotal = diffNow
    ? diffNow.added.length + diffNow.removed.length + diffNow.changed.length
    : 0;

  return (
    <div
      className={`min-h-screen lg:grid lg:transition-[grid-template-columns] lg:duration-300 motion-reduce:transition-none ${
        sidebarOpen ? "lg:grid-cols-[300px_1fr]" : "lg:grid-cols-[0px_1fr]"
      }`}
    >
      <div
        id="scan-history"
        inert={!sidebarOpen}
        className={`min-w-0 overflow-hidden lg:sticky lg:top-0 lg:h-screen ${
          sidebarOpen ? "" : "max-lg:hidden"
        }`}
      >
      <Sidebar
        email={email}
        scans={scans}
        selectedId={selectedId}
        onSelect={(id) => {
          setSelectedId(id);
          setTab("hosts");
          setActiveHost(null);
          setNotice(null);
        }}
        onDelete={removeScan}
        onLogout={logout}
      />
      </div>

      <main className="min-w-0 px-5 py-8 lg:px-10">
        <button
          type="button"
          onClick={toggleSidebar}
          aria-expanded={sidebarOpen}
          aria-controls="scan-history"
          className="mb-6 inline-flex items-center gap-2 rounded-lg border border-reef px-3 py-1.5 text-sm text-mist hover:bg-trench-2 hover:text-foam"
        >
          <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
            <rect x="2.5" y="3.5" width="15" height="13" rx="2" />
            <path d="M8 3.5v13" />
            {sidebarOpen ? <path d="M13.5 8.5 11.5 10l2 1.5" /> : <path d="M11.5 8.5 13.5 10l-2 1.5" />}
          </svg>
          {sidebarOpen ? "Hide history" : "Show history"}
        </button>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (target && authorized && !busy) startScan(target, false);
          }}
          className="max-w-3xl"
        >
          <label htmlFor="domain" className="text-sm font-medium">
            Domain to scan
          </label>
          <div className="mt-1.5 flex gap-3">
            <input
              id="domain"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="example.com"
              autoComplete="off"
              spellCheck={false}
              className="min-w-0 flex-1 rounded-lg border border-reef bg-trench px-3.5 py-2.5 font-mono placeholder:text-mist/60"
            />
            <button
              type="submit"
              disabled={busy || !target || !authorized}
              className="rounded-lg bg-sonar px-5 py-2.5 font-semibold text-sea disabled:opacity-40"
            >
              {busy ? "Starting..." : "Start scan"}
            </button>
          </div>
          <label className="mt-3 flex items-start gap-2.5 text-sm text-mist">
            <input
              type="checkbox"
              checked={authorized}
              onChange={(e) => setAuthorized(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-sonar"
            />
            I own this domain or have permission to scan it.
          </label>
        </form>

        {error && (
          <p role="alert" className="mt-5 max-w-3xl rounded-lg bg-coral/15 px-4 py-3 text-coral">
            {error}
          </p>
        )}
        {notice && (
          <p className="mt-5 max-w-3xl rounded-lg bg-sonar/10 px-4 py-3 text-sonar">{notice}</p>
        )}

        {!current ? (
          <section className="mt-12 max-w-xl">
            <h1 className="text-3xl font-semibold tracking-tight">
              {scans.length ? "Pick a scan from your history" : "Run your first scan"}
            </h1>
            <p className="mt-3 text-lg text-mist">
              {scans.length
                ? "Open any scan on the left to see its hosts and what changed since the scan before it."
                : "Enter a domain you own above. You will see every subdomain that answers, and the next scan will show what changed."}
            </p>
          </section>
        ) : (
          <>
            <section className="mt-8 grid gap-8 rounded-2xl bg-trench p-6 lg:grid-cols-[340px_1fr] lg:p-8">
              <div className="flex justify-center lg:justify-start">
                <Sonar
                  domain={current.target_domain}
                  assets={assets}
                  newHosts={newHosts}
                  scanning={scanning}
                  activeHost={activeHost}
                  onPick={pickHost}
                />
              </div>

              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="break-all font-mono text-3xl font-medium tracking-tight">
                    {current.target_domain}
                  </h1>
                  {pill && (
                    <span className={`rounded-full px-3 py-1 text-sm font-medium ${pill.cls}`}>
                      {pill.text}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-mist">
                  Started {formatWhen(scans.find((s) => s.job_id === current.job_id)?.created_at ?? null)}.{" "}
                  {prevScan
                    ? `Compared with the scan from ${formatWhen(prevScan.created_at)}.`
                    : status === "COMPLETED"
                      ? "This is the first finished scan of this domain."
                      : ""}
                </p>

                {current.error && (
                  <p
                    role={current.status === "FAILED" ? "alert" : undefined}
                    className={`mt-4 rounded-lg px-4 py-3 text-sm ${
                      current.status === "FAILED" ? "bg-coral/15 text-coral" : "bg-flare/10 text-flare"
                    }`}
                  >
                    {current.status === "FAILED" ? "The scan failed: " : "Note: "}
                    {current.error}
                  </p>
                )}

                {scanning && (
                  <p className="mt-4 text-flare" aria-live="polite">
                    {current.status === "QUEUED"
                      ? "Waiting for the scan worker to pick this up."
                      : "Looking for subdomains and checking which ones answer. This page updates by itself."}
                  </p>
                )}
                {scanning && current.status === "QUEUED" && stalledId === current.job_id && (
                  <p className="mt-2 rounded-lg bg-flare/10 px-4 py-3 text-sm text-flare">
                    This is taking longer than expected. The scan worker is probably not running.
                    Start it with <code className="font-mono">celery -A app.celery_app worker --loglevel=info</code>{" "}
                    and Redis with <code className="font-mono">redis-server</code>, or press Stop scan.
                  </p>
                )}

                <dl className="mt-6 grid grid-cols-2 border-y border-reef/60 sm:grid-cols-5 sm:divide-x sm:divide-reef/60">
                  <Stat label="Hosts found" value={scanning ? dash : assets.length} />
                  <Stat label="With a web service" value={scanning ? dash : webCount} />
                  <Stat label="New" value={diffNow ? diffNow.added.length : dash} tone="text-kelp" />
                  <Stat label="Changed" value={diffNow ? diffNow.changed.length : dash} tone="text-flare" />
                  <Stat label="Gone" value={diffNow ? diffNow.removed.length : dash} tone="text-coral" />
                </dl>

                <div className="mt-5 flex flex-wrap gap-3">
                  {scanning ? (
                    <button
                      onClick={stopScan}
                      className="rounded-lg border border-coral px-4 py-2 text-sm font-semibold text-coral hover:bg-coral/15"
                    >
                      Stop scan
                    </button>
                  ) : (
                    <button
                      onClick={() => startScan(current.target_domain, true)}
                      disabled={busy || !authorized}
                      title={authorized ? undefined : "Tick the permission box above first"}
                      className="rounded-lg bg-sonar px-4 py-2 text-sm font-semibold text-sea disabled:opacity-40"
                    >
                      Scan again
                    </button>
                  )}
                  <button
                    onClick={() => exportView("csv")}
                    disabled={scanning || !assets.length}
                    className="rounded-lg border border-reef px-4 py-2 text-sm hover:bg-trench-2 disabled:opacity-40"
                  >
                    Export CSV
                  </button>
                  <button
                    onClick={() => exportView("json")}
                    disabled={scanning || !assets.length}
                    className="rounded-lg border border-reef px-4 py-2 text-sm hover:bg-trench-2 disabled:opacity-40"
                  >
                    Export JSON
                  </button>
                </div>
              </div>
            </section>

            <div role="tablist" aria-label="Scan results" className="mt-10 flex gap-6 border-b border-reef">
              <TabButton active={tab === "hosts"} onClick={() => setTab("hosts")}>
                Hosts <span className="text-mist">{assets.length}</span>
              </TabButton>
              <TabButton active={tab === "changes"} onClick={() => setTab("changes")}>
                Changes{" "}
                {changeTotal > 0 && (
                  <span className="rounded-full bg-flare/15 px-2 py-0.5 text-xs text-flare">{changeTotal}</span>
                )}
              </TabButton>
            </div>

            <div className="mt-6">
              {tab === "hosts" ? (
                scanning ? (
                  <p className="text-mist">Results appear here as soon as the scan finishes.</p>
                ) : assets.length === 0 ? (
                  <p className="max-w-xl text-mist">
                    {current.status === "FAILED"
                      ? "No results were saved. Fix the problem above and scan again."
                      : current.status === "CANCELLED"
                        ? "You stopped this scan, so no results were saved. Press Scan again to run it fully."
                        : "No hosts answered. Check the domain spelling, or try again later."}
                  </p>
                ) : (
                  <HostTable
                    assets={assets}
                    newHosts={newHosts}
                    changedHosts={changedHosts}
                    activeHost={activeHost}
                    onActive={setActiveHost}
                    onVisibleChange={onVisibleChange}
                  />
                )
              ) : (
                <ChangesPanel
                  diff={diffNow}
                  loading={diffLoading}
                  previousWhen={prevScan ? formatWhen(prevScan.created_at) : null}
                  error={diffError}
                  onPick={pickHost}
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="px-4 py-4 first:pl-0">
      <dd className={`text-3xl font-semibold tabular-nums ${tone ?? "text-foam"}`}>{value}</dd>
      <dt className="mt-0.5 text-sm text-mist">{label}</dt>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`-mb-px border-b-2 pb-3 text-base font-medium ${
        active ? "border-sonar text-foam" : "border-transparent text-mist hover:text-foam"
      }`}
    >
      {children}
    </button>
  );
}
