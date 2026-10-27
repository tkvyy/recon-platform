"use client";

import { useState } from "react";
import { ApiError, api } from "../lib/api";

type Props = { onAuthed: (token: string, email: string) => void };

export default function AuthPanel({ onAuthed }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") await api.register(email, password);
      const { access_token } = await api.login(email, password);
      onAuthed(access_token, email.trim().toLowerCase());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const registering = mode === "register";

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-trench lg:block">
        <svg
          viewBox="0 0 360 360"
          aria-hidden="true"
          className="absolute -right-40 top-1/2 h-[900px] w-[900px] -translate-y-1/2"
        >
          {[40, 74, 108, 142, 176].map((r, i) => (
            <circle
              key={r}
              cx="180"
              cy="180"
              r={r}
              fill="none"
              stroke="#23566c"
              strokeWidth="0.8"
              strokeDasharray={i % 2 ? "3 5" : undefined}
            />
          ))}
          <g className="sonar-sweep">
            <path d="M180 180 L180 4 A176 176 0 0 1 268 27.5 Z" fill="#3fd8e0" opacity="0.14" />
            <line x1="180" y1="180" x2="268" y2="27.5" stroke="#3fd8e0" strokeWidth="1.2" />
          </g>
          {[
            [250, 120, "#5be3a3"], [120, 90, "#3fd8e0"], [300, 210, "#ffb84d"],
            [90, 230, "#5be3a3"], [210, 285, "#ff6b7a"], [150, 150, "#3fd8e0"],
            [230, 190, "#5be3a3"], [60, 150, "#4d7380"],
          ].map(([x, y, fill]) => (
            <circle key={`${x}-${y}`} cx={x as number} cy={y as number} r="4.5" fill={fill as string} />
          ))}
          <circle cx="180" cy="180" r="8" fill="#e8f6f3" />
        </svg>

        <div className="relative z-10 flex h-full max-w-xl flex-col justify-between p-14">
          <p className="text-lg font-semibold tracking-tight text-foam">
            Attack Surface Recon
          </p>
          <div>
            <h1 className="text-5xl font-semibold leading-[1.05] tracking-tight text-foam">
              Scan once.
              <br />
              Know what changed.
            </h1>
            <p className="mt-5 max-w-md text-lg leading-relaxed text-mist">
              Every scan is saved to your account, so you compare results
              instead of repeating the same commands.
            </p>
          </div>
          <p className="max-w-sm text-sm text-mist">
            Only scan domains you own or have permission to test.
          </p>
        </div>
      </section>

      <section className="flex items-center justify-center px-6 py-16">
        <form onSubmit={submit} className="w-full max-w-sm" noValidate>
          <h2 className="text-3xl font-semibold tracking-tight">
            {registering ? "Create your account" : "Log in"}
          </h2>
          <p className="mt-2 text-mist">
            {registering
              ? "Your scans stay private to your account."
              : "Pick up where your last scan left off."}
          </p>

          <label className="mt-8 block text-sm font-medium" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-reef bg-trench px-3.5 py-2.5 text-foam placeholder:text-mist/60"
            placeholder="you@example.com"
          />

          <label className="mt-5 block text-sm font-medium" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete={registering ? "new-password" : "current-password"}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-reef bg-trench px-3.5 py-2.5 text-foam"
          />
          {registering && (
            <p className="mt-1.5 text-xs text-mist">Use at least 8 characters.</p>
          )}

          {error && (
            <p role="alert" className="mt-5 rounded-lg bg-coral/15 px-3.5 py-2.5 text-sm text-coral">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !email || !password}
            className="mt-7 w-full rounded-lg bg-sonar px-4 py-3 font-semibold text-sea transition-opacity disabled:opacity-40"
          >
            {busy ? "Please wait..." : registering ? "Create account" : "Log in"}
          </button>

          <p className="mt-6 text-sm text-mist">
            {registering ? "Already have an account?" : "New here?"}{" "}
            <button
              type="button"
              className="font-medium text-sonar underline underline-offset-4"
              onClick={() => {
                setMode(registering ? "login" : "register");
                setError(null);
              }}
            >
              {registering ? "Log in" : "Create an account"}
            </button>
          </p>
        </form>
      </section>
    </main>
  );
}
