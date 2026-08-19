/**
 * Command Center — what the account looks like right now, at a glance.
 *
 * Ordered by what a marketing lead needs first: headline KPIs, then what
 * changed over time, then where the money sits, then what needs a decision,
 * then the full campaign table.
 */

import React, { useState } from 'react';
import { useHelm } from '../store';
import { ContextBar } from '../components/Shell';
import { ChannelBars, ScoreBar, Sparkline, TrendChart, SERIES } from '../components/Charts';
import { Button, Chip, Icon, Spinner, formatCompact, formatINR } from '../components/ui';

const METRICS = [
  { key: 'spend', label: 'Spend', format: 'currency', color: SERIES[0] },
  { key: 'conversions', label: 'Conversions', format: 'number', color: SERIES[2] },
  { key: 'roas', label: 'ROAS', format: 'multiple', color: SERIES[1] },
  { key: 'cpa', label: 'CPA', format: 'currency', color: SERIES[3] },
];

export function OverviewScreen() {
  const { overview, loading, refreshOverview, set } = useHelm();
  const [metric, setMetric] = useState(METRICS[0]);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = async () => {
    setRefreshing(true);
    await refreshOverview();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <>
        <ContextBar title="Command Center" />
        <div className="flex justify-center py-24 text-primary">
          <Spinner className="w-7 h-7" />
        </div>
      </>
    );
  }

  if (!overview || overview.error) {
    return (
      <>
        <ContextBar title="Command Center" />
        <div className="p-7">
          <div className="card p-6 border-error/30 bg-error-container">
            <p className="font-headline text-headline-md text-on-error-container mb-1">
              Could not load account data
            </p>
            <p className="text-body-sm text-on-error-container/90">
              {overview?.error || 'The API is unreachable. Is the server running?'}
            </p>
            <Button variant="secondary" icon="refresh" className="mt-4" onClick={refresh}>
              Retry
            </Button>
          </div>
        </div>
      </>
    );
  }

  const alerts = overview.alerts || [];
  const critical = alerts.filter((a) => a.severity === 'critical');

  return (
    <>
      <ContextBar
        title="Command Center"
        subtitle={`Last ${overview.period_days} days · ${overview.campaigns.length} campaigns`}
        actions={
          <Button variant="secondary" size="sm" icon="refresh" onClick={refresh} disabled={refreshing}>
            {refreshing ? 'Refreshing' : 'Refresh'}
          </Button>
        }
      />

      <div className="p-4 sm:p-7 space-y-6 max-w-[1400px]">
        {/* Pending approvals sit above everything — they block money moving. */}
        {overview.pending_approvals?.length > 0 && (
          <button
            onClick={() => set({ screen: 'pipeline' })}
            className="w-full flex items-center gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-left hover:bg-amber-100 transition-colors focus-ring"
          >
            <Icon name="pending_actions" size={20} className="text-amber-700 shrink-0" fill />
            <span className="flex-1 min-w-0">
              <span className="block font-headline text-body-md font-semibold text-amber-900">
                {overview.pending_approvals.length} proposal
                {overview.pending_approvals.length === 1 ? '' : 's'} awaiting your approval
              </span>
              <span className="block text-body-sm text-amber-800/90 truncate">
                {overview.pending_approvals[0].objective}
              </span>
            </span>
            <Icon name="arrow_forward" size={18} className="text-amber-700 shrink-0" />
          </button>
        )}

        {/* Headline KPIs */}
        <section>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {overview.kpis.map((kpi) => (
              <KpiTile key={kpi.key} kpi={kpi} series={overview.timeseries} />
            ))}
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
            {overview.secondary_kpis.map((kpi) => (
              <div key={kpi.key} className="card px-4 py-3 flex items-baseline justify-between gap-2">
                <span className="rail-label">{kpi.label}</span>
                <span className="font-headline text-body-md font-semibold text-on-surface tabular-nums">
                  {formatValue(kpi.value, kpi.format)}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Trend + channel split */}
        <section className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="card p-5 xl:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <h2 className="font-headline text-headline-md text-on-surface">
                {metric.label} over time
              </h2>
              <div
                className="flex gap-1 p-0.5 rounded-lg bg-surface-container"
                role="tablist"
                aria-label="Metric"
              >
                {METRICS.map((m) => (
                  <button
                    key={m.key}
                    role="tab"
                    aria-selected={metric.key === m.key}
                    onClick={() => setMetric(m)}
                    className={`px-2.5 py-1 rounded-md text-body-sm font-medium transition-colors focus-ring ${
                      metric.key === m.key
                        ? 'bg-surface-container-lowest text-on-surface shadow-sm'
                        : 'text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>
            <TrendChart
              data={overview.timeseries}
              metric={metric.key}
              label={metric.label}
              format={metric.format}
              color={metric.color}
              height={230}
            />
          </div>

          <div className="card p-5">
            <h2 className="font-headline text-headline-md text-on-surface mb-4">Where spend sits</h2>
            <ChannelBars channels={overview.channels} />
          </div>
        </section>

        {/* Alerts */}
        {alerts.length > 0 && (
          <section className="card p-5">
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className="font-headline text-headline-md text-on-surface">
                Signals needing attention
              </h2>
              {critical.length > 0 && (
                <span className="chip bg-red-50 text-red-800 border border-red-200">
                  {critical.length} critical
                </span>
              )}
            </div>
            <ul className="space-y-2.5">
              {alerts.map((alert, index) => (
                <AlertRow key={index} alert={alert} />
              ))}
            </ul>
            <Button
              variant="secondary"
              size="sm"
              icon="query_stats"
              className="mt-4"
              onClick={() => set({ screen: 'agents', activeAgent: 'analyst' })}
            >
              Ask the Analyst about these
            </Button>
          </section>
        )}

        {/* Campaign table */}
        <section className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-outline-variant/40 flex items-center justify-between gap-3">
            <h2 className="font-headline text-headline-md text-on-surface">Campaign performance</h2>
            <span className="rail-label">Ranked by composite score</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-body-sm">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/40">
                  <th className="px-5 py-2.5 rail-label text-left">Campaign</th>
                  <th className="px-4 py-2.5 rail-label text-left">Platform</th>
                  <th className="px-4 py-2.5 rail-label text-right">Spend</th>
                  <th className="px-4 py-2.5 rail-label text-right">ROAS</th>
                  <th className="px-4 py-2.5 rail-label text-right">CPA</th>
                  <th className="px-4 py-2.5 rail-label text-right">CTR</th>
                  <th className="px-4 py-2.5 rail-label text-right">Conv.</th>
                  <th className="px-4 py-2.5 rail-label text-left">Score</th>
                  <th className="px-5 py-2.5 rail-label text-center">Verdict</th>
                </tr>
              </thead>
              <tbody>
                {overview.campaigns.map((c) => (
                  <tr
                    key={c.campaign_id}
                    className="border-b border-outline-variant/25 last:border-0 hover:bg-surface-container-low/60 transition-colors"
                  >
                    <td className="px-5 py-3 text-on-surface font-medium max-w-[280px] truncate">
                      {c.campaign_name}
                    </td>
                    <td className="px-4 py-3 text-on-surface-variant whitespace-nowrap">
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className="w-2 h-2 rounded-sm shrink-0"
                          style={{
                            background: c.platform === 'google_ads' ? SERIES[0] : SERIES[1],
                          }}
                        />
                        {c.platform_label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium text-on-surface-variant">
                      {formatINR(c.spend_inr)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium text-on-surface-variant">
                      {c.roas}x
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-on-surface-variant">
                      {formatINR(c.cpa_inr)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-on-surface-variant">
                      {c.ctr}%
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-on-surface-variant">
                      {formatCompact(c.conversions)}
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBar score={c.score} />
                    </td>
                    <td className="px-5 py-3 text-center">
                      <Chip label={c.verdict} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </>
  );
}

function KpiTile({ kpi, series }) {
  const positive = kpi.improved;
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="rail-label">{kpi.label}</span>
        {series?.length > 1 && (
          <Sparkline
            data={series}
            metric={kpi.key === 'conversions' ? 'conversions' : kpi.key}
            color={positive === false ? '#d03b3b' : SERIES[0]}
          />
        )}
      </div>
      <p className="font-headline text-headline-xl text-on-surface leading-none">
        {formatValue(kpi.value, kpi.format)}
      </p>
      {kpi.delta_pct !== undefined && (
        <p
          className={`mt-2 inline-flex items-center gap-1 font-mono text-[11px] font-semibold ${
            positive ? 'text-viz-good' : 'text-viz-critical'
          }`}
        >
          <Icon name={kpi.delta_pct >= 0 ? 'trending_up' : 'trending_down'} size={13} />
          {kpi.delta_pct > 0 ? '+' : ''}
          {kpi.delta_pct}%
          <span className="text-viz-muted font-normal ml-0.5">vs prior period</span>
        </p>
      )}
    </div>
  );
}

const ALERT_TONES = {
  critical: { icon: 'error', className: 'text-viz-critical', chip: 'bg-red-50 text-red-800 border-red-200' },
  warning: { icon: 'warning', className: 'text-amber-600', chip: 'bg-amber-50 text-amber-800 border-amber-200' },
  opportunity: { icon: 'trending_up', className: 'text-viz-good', chip: 'bg-green-50 text-green-800 border-green-200' },
};

function AlertRow({ alert }) {
  const tone = ALERT_TONES[alert.severity] || ALERT_TONES.warning;
  return (
    <li className="flex gap-3 p-3 rounded-lg border border-outline-variant/40 bg-surface-container-low/50">
      <Icon name={tone.icon} size={18} className={`${tone.className} shrink-0 mt-0.5`} fill />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span className="font-headline text-body-md font-semibold text-on-surface">
            {alert.title}
          </span>
          <span className={`chip border ${tone.chip}`}>{alert.severity}</span>
        </div>
        <p className="text-body-sm text-on-surface-variant leading-relaxed">{alert.detail}</p>
      </div>
    </li>
  );
}

function formatValue(value, format) {
  const num = Number(value) || 0;
  if (format === 'currency') return formatINR(num);
  if (format === 'multiple') return `${num}x`;
  if (format === 'percent') return `${num}%`;
  return formatCompact(num);
}
