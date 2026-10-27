"use client";

import { useMemo, useState } from "react";
import type { Asset } from "../lib/api";
import { STATUS_STYLE, hash32, hostDepth, statusClass } from "../lib/format";
import type { StatusClass } from "../lib/format";

const C = 180; // centre of the 360 x 360 viewBox
const ringRadius = (depth: number) => 38 + depth * 34;

type Props = {
  domain: string;
  assets: Asset[];
  newHosts: Set<string>;
  scanning: boolean;
  activeHost: string | null;
  onPick: (host: string) => void;
};

export default function Sonar({
  domain,
  assets,
  newHosts,
  scanning,
  activeHost,
  onPick,
}: Props) {
  const [hover, setHover] = useState<string | null>(null);

  const dots = useMemo(
    () =>
      assets.map((a) => {
        const depth = Math.min(hostDepth(a.hostname, domain), 4);
        const h = hash32(a.hostname);
        const angle = (h / 2 ** 32) * Math.PI * 2;
        const jitter = (((h >>> 8) % 100) / 100 - 0.5) * 14;
        const r = depth === 0 ? 0 : ringRadius(depth) + jitter;
        return {
          host: a.hostname,
          depth,
          cls: statusClass(a.http_status),
          code: a.http_status,
          x: C + r * Math.cos(angle),
          y: C + r * Math.sin(angle),
        };
      }),
    [assets, domain],
  );

  const maxDepth = Math.max(2, ...dots.map((d) => d.depth));
  const shown = hover ?? activeHost;
  const shownDot = dots.find((d) => d.host === shown);
  const legend: StatusClass[] = ["2xx", "3xx", "4xx", "5xx", "none"];

  return (
    <div className="w-full max-w-[340px]">
      <svg
        viewBox="0 0 360 360"
        role="img"
        aria-label={`Map of ${assets.length} hosts found for ${domain}`}
        className="block w-full"
      >
        {Array.from({ length: maxDepth }, (_, i) => i + 1).map((d) => (
          <circle
            key={d}
            cx={C}
            cy={C}
            r={ringRadius(d)}
            fill="none"
            stroke="#23566c"
            strokeWidth="1"
            strokeDasharray={d % 2 ? undefined : "3 5"}
          />
        ))}
        <line x1={C} y1="6" x2={C} y2="354" stroke="#23566c" strokeWidth="0.5" opacity="0.5" />
        <line x1="6" y1={C} x2="354" y2={C} stroke="#23566c" strokeWidth="0.5" opacity="0.5" />

        {scanning && (
          <g className="sonar-sweep">
            <path d="M180 180 L180 6 A174 174 0 0 1 267 29.3 Z" fill="#3fd8e0" opacity="0.16" />
            <line x1="180" y1="180" x2="267" y2="29.3" stroke="#3fd8e0" strokeWidth="1.5" />
          </g>
        )}

        {dots.map((d) => {
          const fill = STATUS_STYLE[d.cls].fill;
          const isApex = d.depth === 0;
          const active = d.host === shown;
          return (
            <g
              key={d.host}
              className="cursor-pointer"
              onMouseEnter={() => setHover(d.host)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onPick(d.host)}
            >
              {newHosts.has(d.host) && (
                <circle
                  className="sonar-ping"
                  cx={d.x}
                  cy={d.y}
                  r="5"
                  fill="none"
                  stroke="#5be3a3"
                  strokeWidth="1.5"
                  style={{ transformOrigin: `${d.x}px ${d.y}px` }}
                />
              )}
              {active && (
                <circle cx={d.x} cy={d.y} r={isApex ? 14 : 10} fill="none" stroke="#e8f6f3" strokeWidth="1.5" />
              )}
              <circle cx={d.x} cy={d.y} r={isApex ? 8 : 5} fill={fill} stroke="#0a2431" strokeWidth="1.5" />
              {/* larger invisible target so small dots are easy to hit */}
              <circle cx={d.x} cy={d.y} r="11" fill="transparent" />
              <title>{d.host}</title>
            </g>
          );
        })}
      </svg>

      <p className="mt-1 min-h-[1.5rem] truncate text-center font-mono text-sm text-foam">
        {shownDot
          ? `${shownDot.host}  ${shownDot.code ?? "no web"}`
          : `${assets.length} hosts mapped. Hover a dot to read it.`}
      </p>

      <ul className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-mist">
        {legend.map((c) => (
          <li key={c} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: STATUS_STYLE[c].fill }}
            />
            {STATUS_STYLE[c].label}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-center text-xs text-mist">
        The center is your domain. Each ring out is one more subdomain level.
      </p>
    </div>
  );
}
