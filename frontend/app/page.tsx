"use client";

import { useEffect, useRef, useState } from "react";

const API = "http://localhost:8000";

type Asset = {
  hostname: string;
  ip_address: string | null;
  http_status: number | null;
  tech_stack: string[];
};

type Scan = {
  job_id: string;
  target_domain: string;
  status: string;
  error: string | null;
  raw_count: number;
  assets: Asset[];
};

export default function Home() {
  const [domain, setDomain] = useState("");
  const [scan, setScan] = useState<Scan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPolling() {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }

  useEffect(() => {
    return () => stopPolling();
  }, []);

  // Fetch the job; returns true once the scan has finished.
  async function poll(jobId: string): Promise<boolean> {
    const res = await fetch(`${API}/scans/${jobId}`);
    const data: Scan = await res.json();
    setScan(data);
    const done = data.status === "COMPLETED" || data.status === "FAILED";
    if (done) {
      stopPolling();
      setBusy(false);
    }
    return done;
  }

  async function startScan() {
    setError(null);
    setScan(null);
    stopPolling();
    setBusy(true);
    try {
      const res = await fetch(`${API}/scans`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(typeof body.detail === "string" ? body.detail : "Invalid request");
        setBusy(false);
        return;
      }
      const { job_id } = await res.json();
      const done = await poll(job_id);
      if (!done) {
        timer.current = setInterval(() => poll(job_id), 3000);
      }
    } catch {
      setError("Cannot reach the API. Is it running on port 8000?");
      setBusy(false);
    }
  }

  const statusColor =
    scan?.status === "COMPLETED"
      ? "bg-green-100 text-green-800"
      : scan?.status === "FAILED"
      ? "bg-red-100 text-red-800"
      : "bg-yellow-100 text-yellow-800";

  return (
    <main className="mx-auto max-w-5xl p-8 text-gray-900">
      <h1 className="text-2xl font-bold">Attack Surface Recon Platform</h1>
      <p className="mt-1 text-sm text-gray-600">
        Only scan domains you own or are authorized to test.
      </p>

      <div className="mt-6 flex gap-3">
        <input
          className="flex-1 rounded border border-gray-300 px-3 py-2"
          placeholder="example.com"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && domain && startScan()}
        />
        <button
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
          onClick={startScan}
          disabled={busy || !domain}
        >
          {busy ? "Scanning..." : "Start scan"}
        </button>
      </div>

      {error && (
        <p className="mt-4 rounded bg-red-100 p-3 text-red-800">{error}</p>
      )}

      {scan && (
        <section className="mt-6">
          <div className="flex items-center gap-3">
            <span className={`rounded px-2 py-1 text-sm font-medium ${statusColor}`}>
              {scan.status}
            </span>
            <span className="text-sm text-gray-600">
              {scan.target_domain} · {scan.raw_count} subdomains found ·{" "}
              {scan.assets.length} live
            </span>
          </div>

          {scan.error && (
            <p className="mt-3 rounded bg-red-100 p-3 text-red-800">{scan.error}</p>
          )}

          {scan.assets.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b bg-gray-100">
                    <th className="p-2">Hostname</th>
                    <th className="p-2">IP</th>
                    <th className="p-2">Status</th>
                    <th className="p-2">Technologies</th>
                  </tr>
                </thead>
                <tbody>
                  {scan.assets.map((a) => (
                    <tr key={a.hostname} className="border-b">
                      <td className="p-2 font-mono">{a.hostname}</td>
                      <td className="p-2">{a.ip_address ?? "-"}</td>
                      <td className="p-2">{a.http_status ?? "-"}</td>
                      <td className="p-2">{(a.tech_stack ?? []).join(", ") || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
