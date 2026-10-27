export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export type Asset = {
  hostname: string;
  ip_address: string | null;
  ips: string[];
  cname: string[];
  scheme: string | null;
  http_status: number | null;
  title: string | null;
  headers: Record<string, string>;
  redirect_url: string | null;
  tech_stack: string[];
  sources: string[];
};

export type ScanSummary = {
  job_id: string;
  target_domain: string;
  status: string;
  created_at: string | null;
  raw_count: number;
  live_count: number;
};

export type Scan = {
  job_id: string;
  target_domain: string;
  status: string;
  error: string | null;
  raw_count: number;
  assets: Asset[];
};

export type Diff = {
  old: string;
  new: string;
  target_domain: string;
  added: string[];
  removed: string[];
  changed: {
    hostname: string;
    changes: Record<string, { old: unknown; new: unknown }>;
  }[];
  unchanged: number;
};

async function request<T>(
  path: string,
  token: string | null,
  init: RequestInit = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch {
    throw new ApiError(
      0,
      "Can't reach the API. Check that it's running on port 8000.",
    );
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : "Something went wrong. Try again.";
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  register: (email: string, password: string) =>
    request<{ id: number; email: string }>("/auth/register", null, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", null, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: (token: string) =>
    request<void>("/auth/logout", token, { method: "POST" }),
  me: (token: string) =>
    request<{ id: number; email: string }>("/auth/me", token),
  listScans: (token: string) =>
    request<ScanSummary[]>("/scans?limit=100", token),
  getScan: (token: string, id: string) =>
    request<Scan>(`/scans/${id}`, token),
  createScan: (token: string, domain: string, force: boolean) =>
    request<{ job_id: string; status: string; reused: boolean }>(
      "/scans",
      token,
      { method: "POST", body: JSON.stringify({ domain, force }) },
    ),
  cancelScan: (token: string, id: string) =>
    request<{ job_id: string; status: string }>(`/scans/${id}/cancel`, token, {
      method: "POST",
    }),
  deleteScan: (token: string, id: string) =>
    request<void>(`/scans/${id}`, token, { method: "DELETE" }),
  diff: (token: string, oldId: string, newId: string) =>
    request<Diff>(`/scans/${oldId}/diff/${newId}`, token),
};
