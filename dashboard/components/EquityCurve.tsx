"use client";

import { motion } from "framer-motion";

type Point = { date: string; equity: number };

const W = 1100;
const H = 380;
const M = { top: 20, right: 24, bottom: 44, left: 78 };

function movingAverage(values: number[], window: number): (number | null)[] {
  return values.map((_, i) =>
    i < window - 1
      ? null
      : values.slice(i - window + 1, i + 1).reduce((a, b) => a + b, 0) / window
  );
}

export default function EquityCurve({ points }: { points: Point[] }) {
  if (points.length < 2) {
    return <p className="empty">Not enough equity history yet.</p>;
  }

  const values = points.map((p) => p.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const yMin = min - span * 0.08;
  const yMax = max + span * 0.08;

  const x = (i: number) => M.left + (i / (points.length - 1)) * (W - M.left - M.right);
  const y = (v: number) => M.top + (1 - (v - yMin) / (yMax - yMin)) * (H - M.top - M.bottom);

  // 5 horizontal gridlines with $ labels
  const yTicks = Array.from({ length: 5 }, (_, i) => yMin + ((yMax - yMin) * i) / 4);
  // ~6 date labels along the x axis
  const step = Math.max(1, Math.round((points.length - 1) / 5));
  const xTicks = points
    .map((p, i) => ({ p, i }))
    .filter(({ i }) => i % step === 0 || i === points.length - 1);

  const equityPath = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const ma = movingAverage(values, 7);
  const maPath = ma
    .map((v, i) => (v === null ? null : `${x(i)},${y(v)}`))
    .filter(Boolean)
    .join(" ");

  const last = values[values.length - 1];

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
        {/* gridlines + y-axis labels */}
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={M.left}
              x2={W - M.right}
              y1={y(v)}
              y2={y(v)}
              stroke="rgba(255,255,255,0.1)"
              strokeDasharray="3 5"
            />
            <text
              x={M.left - 12}
              y={y(v) + 4}
              textAnchor="end"
              fill="var(--dim)"
              fontSize="12"
              fontWeight="600"
            >
              ${Math.round(v).toLocaleString()}
            </text>
          </g>
        ))}

        {/* x-axis ticks + date labels */}
        {xTicks.map(({ p, i }) => (
          <g key={p.date}>
            <line
              x1={x(i)}
              x2={x(i)}
              y1={M.top}
              y2={H - M.bottom}
              stroke="rgba(255,255,255,0.05)"
            />
            <text
              x={x(i)}
              y={H - M.bottom + 24}
              textAnchor="middle"
              fill="var(--dim)"
              fontSize="12"
              fontWeight="600"
            >
              {p.date.slice(5)}
            </text>
          </g>
        ))}

        {/* axis lines */}
        <line
          x1={M.left}
          x2={M.left}
          y1={M.top}
          y2={H - M.bottom}
          stroke="rgba(255,255,255,0.35)"
        />
        <line
          x1={M.left}
          x2={W - M.right}
          y1={H - M.bottom}
          y2={H - M.bottom}
          stroke="rgba(255,255,255,0.35)"
        />

        {/* area fill under equity */}
        <polygon
          points={`${M.left},${H - M.bottom} ${equityPath} ${W - M.right},${H - M.bottom}`}
          fill="rgba(255,255,255,0.05)"
        />

        {/* 7-day moving average (dashed) */}
        {maPath && (
          <motion.polyline
            fill="none"
            stroke="rgba(255,255,255,0.45)"
            strokeWidth="1.5"
            strokeDasharray="6 6"
            points={maPath}
            initial={{ pathLength: 0 }}
            whileInView={{ pathLength: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1.8, ease: "easeOut", delay: 0.4 }}
          />
        )}

        {/* equity line */}
        <motion.polyline
          fill="none"
          stroke="var(--fg)"
          strokeWidth="2.2"
          points={equityPath}
          initial={{ pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 1.8, ease: "easeOut" }}
        />

        {/* endpoint marker */}
        <circle cx={x(values.length - 1)} cy={y(last)} r="4.5" fill="var(--fg)" />
      </svg>

      <div
        style={{
          display: "flex",
          gap: 28,
          fontSize: 13,
          color: "var(--dim)",
          fontWeight: 600,
          marginTop: 12,
        }}
      >
        <span>
          <span
            style={{
              display: "inline-block",
              width: 22,
              height: 2,
              background: "var(--fg)",
              verticalAlign: "middle",
              marginRight: 8,
            }}
          />
          Equity
        </span>
        <span>
          <span
            style={{
              display: "inline-block",
              width: 22,
              borderTop: "2px dashed rgba(255,255,255,0.45)",
              verticalAlign: "middle",
              marginRight: 8,
            }}
          />
          7-day average
        </span>
      </div>
    </div>
  );
}
