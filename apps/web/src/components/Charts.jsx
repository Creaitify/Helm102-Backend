/**
 * Charts — hand-built SVG, no charting library.
 *
 * Conventions applied throughout (from the console's data-viz rules):
 *   - Categorical hue is assigned by slot in fixed order, never cycled.
 *   - One y-axis per chart. Two measures of different scale get two charts.
 *   - Marks are thin; grid and axes are recessive; labels are selective.
 *   - Every series is directly labelled or legended, so identity is never
 *     carried by color alone.
 *   - Line/area charts ship a crosshair tooltip; bars label their own value.
 */

import React, { useMemo, useRef, useState } from 'react';
import { formatINR } from './ui';

export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'];
export const STATUS = {
  good: '#0ca30c',
  warning: '#fab219',
  serious: '#ec835a',
  critical: '#d03b3b',
};

const GRID = '#e1e0d9';
const AXIS = '#c3c2b7';
const MUTED = '#898781';

/* ------------------------------------------------------------------ */
/* Trend chart — area + line with a crosshair tooltip                  */
/* ------------------------------------------------------------------ */

export function TrendChart({
  data = [],
  metric = 'spend',
  label = 'Spend',
  format = 'currency',
  height = 220,
  color = SERIES[0],
}) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);

  const geometry = useMemo(() => {
    if (data.length < 2) return null;

    const values = data.map((d) => Number(d[metric]) || 0);
    const max = Math.max(...values);
    const min = Math.min(...values);
    // Pad the top so the peak never touches the frame; anchor at 0 when the
    // series is all-positive, so area magnitude stays honest.
    const top = max + (max - min || max || 1) * 0.15;
    const bottom = min >= 0 ? 0 : min - (max - min) * 0.15;
    const span = top - bottom || 1;

    const pad = { top: 12, right: 12, bottom: 26, left: 54 };
    const w = 100;
    const innerW = w - pad.left - pad.right;
    const innerH = height - pad.top - pad.bottom;

    const points = values.map((value, index) => ({
      index,
      value,
      x: pad.left + (index / (values.length - 1)) * innerW,
      y: pad.top + innerH - ((value - bottom) / span) * innerH,
      raw: data[index],
    }));

    return { points, pad, innerW, innerH, top, bottom, span, max, min };
  }, [data, metric, height]);

  if (!geometry) {
    return (
      <div
        className="flex items-center justify-center text-body-sm text-outline"
        style={{ height }}
      >
        Not enough data points to plot a trend.
      </div>
    );
  }

  const { points, pad, innerH } = geometry;
  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x} ${p.y}`).join(' ');
  const areaPath = `${linePath} L${points[points.length - 1].x} ${pad.top + innerH} L${points[0].x} ${
    pad.top + innerH
  } Z`;

  const ticks = [0, 0.5, 1].map((t) => ({
    y: pad.top + innerH - t * innerH,
    value: geometry.bottom + t * geometry.span,
  }));

  const gradientId = `trend-${metric}`;

  const onMove = (event) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    // The viewBox is 100 wide, so map pointer x into that space.
    const vx = ((event.clientX - rect.left) / rect.width) * 100;
    let closest = points[0];
    for (const point of points) {
      if (Math.abs(point.x - vx) < Math.abs(closest.x - vx)) closest = point;
    }
    setHover(closest);
  };

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 100 ${height}`}
        preserveAspectRatio="none"
        className="w-full block"
        style={{ height }}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        role="img"
        aria-label={`${label} over ${data.length} days`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.22" />
            <stop offset="100%" stopColor={color} stopOpacity="0.01" />
          </linearGradient>
        </defs>

        {ticks.map((tick, i) => (
          <line
            key={i}
            x1={pad.left}
            x2={100 - pad.right}
            y1={tick.y}
            y2={tick.y}
            stroke={GRID}
            strokeWidth="0.5"
            vectorEffect="non-scaling-stroke"
          />
        ))}

        <path d={areaPath} fill={`url(#${gradientId})`} />
        <path
          d={linePath}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />

        {hover && (
          <>
            <line
              x1={hover.x}
              x2={hover.x}
              y1={pad.top}
              y2={pad.top + innerH}
              stroke={AXIS}
              strokeWidth="1"
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
            {/* A surface ring keeps the marker legible over the line. */}
            <circle cx={hover.x} cy={hover.y} r="4" fill="#ffffff" vectorEffect="non-scaling-stroke" />
            <circle
              cx={hover.x}
              cy={hover.y}
              r="3"
              fill={color}
              stroke="#ffffff"
              strokeWidth="1.5"
              vectorEffect="non-scaling-stroke"
            />
          </>
        )}
      </svg>

      {/* Axis labels sit outside the stretched SVG so text is never distorted. */}
      <div
        className="absolute left-0 top-0 flex flex-col justify-between pointer-events-none font-mono text-[10px] text-viz-muted tabular-nums"
        style={{ height: innerH + 12, paddingTop: 6 }}
      >
        {[...ticks].reverse().map((tick, i) => (
          <span key={i}>{formatMetric(tick.value, format, true)}</span>
        ))}
      </div>

      <div className="flex justify-between font-mono text-[10px] text-viz-muted mt-1 px-1">
        <span>{shortDate(data[0]?.date)}</span>
        <span>{shortDate(data[data.length - 1]?.date)}</span>
      </div>

      {hover && (
        <div
          className="absolute -top-1 pointer-events-none bg-inverse-surface text-inverse-on-surface rounded-lg px-2.5 py-1.5 shadow-lg z-10 whitespace-nowrap"
          style={{
            left: `${Math.min(Math.max(hover.x, 12), 84)}%`,
            transform: 'translateX(-50%)',
          }}
        >
          <div className="font-mono text-[10px] opacity-70">{shortDate(hover.raw?.date)}</div>
          <div className="text-body-sm font-semibold tabular-nums">
            {formatMetric(hover.value, format)}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Channel split — directly labelled horizontal bars                   */
/* ------------------------------------------------------------------ */

export function ChannelBars({ channels = [] }) {
  if (!channels.length) return null;
  const max = Math.max(...channels.map((c) => Number(c.spend_inr) || 0)) || 1;

  return (
    <ul className="space-y-3">
      {channels.map((channel, index) => (
        <li key={channel.key}>
          <div className="flex items-baseline justify-between gap-3 mb-1.5">
            <span className="flex items-center gap-2 text-body-sm font-medium text-on-surface">
              <span
                className="w-2.5 h-2.5 rounded-sm shrink-0"
                style={{ background: SERIES[index % SERIES.length] }}
              />
              {channel.label}
            </span>
            <span className="font-mono text-[11px] text-on-surface-variant tabular-nums">
              {formatINR(channel.spend_inr)} · {channel.share}%
            </span>
          </div>
          <div className="h-2 rounded-full bg-surface-container overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.max((Number(channel.spend_inr) / max) * 100, 1.5)}%`,
                background: SERIES[index % SERIES.length],
              }}
            />
          </div>
          <div className="flex gap-4 mt-1.5 font-mono text-[10px] text-viz-muted tabular-nums">
            <span>{channel.campaign_count} campaigns</span>
            <span>{channel.roas}x ROAS</span>
            <span>{formatINR(channel.cpa_inr)} CPA</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ */
/* Sparkline — bare trend shape for a stat tile                        */
/* ------------------------------------------------------------------ */

export function Sparkline({ data = [], metric = 'spend', color = SERIES[0], width = 88, height = 26 }) {
  if (data.length < 2) return null;

  const values = data.map((d) => Number(d[metric]) || 0);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;

  const path = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - 2 - ((value - min) / span) * (height - 4);
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden="true">
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Score bar — one campaign's composite score, 0-100                   */
/* ------------------------------------------------------------------ */

export function ScoreBar({ score = 0 }) {
  const value = Math.max(0, Math.min(100, Number(score) || 0));
  const color = value >= 65 ? STATUS.good : value >= 40 ? STATUS.warning : STATUS.critical;

  return (
    <span className="inline-flex items-center gap-2">
      <span className="w-14 h-1.5 rounded-full bg-surface-container overflow-hidden">
        <span className="block h-full rounded-full" style={{ width: `${value}%`, background: color }} />
      </span>
      <span className="font-mono text-[11px] text-on-surface-variant tabular-nums w-6 text-right">
        {Math.round(value)}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */

function formatMetric(value, format, compact = false) {
  const num = Number(value) || 0;
  if (format === 'currency') {
    if (compact) {
      if (Math.abs(num) >= 1e7) return `₹${(num / 1e7).toFixed(1)}Cr`;
      if (Math.abs(num) >= 1e5) return `₹${(num / 1e5).toFixed(1)}L`;
      if (Math.abs(num) >= 1e3) return `₹${(num / 1e3).toFixed(0)}K`;
      return `₹${Math.round(num)}`;
    }
    return formatINR(num);
  }
  if (format === 'multiple') return `${num.toFixed(2)}x`;
  if (format === 'percent') return `${num.toFixed(2)}%`;
  if (compact && Math.abs(num) >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toLocaleString('en-IN');
}

function shortDate(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return String(iso);
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

export { formatMetric };
