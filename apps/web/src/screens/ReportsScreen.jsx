/** Reports: generate, browse, and read full account analysis documents. */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { Button, Chip, EmptyState, Icon, Spinner, formatCompact, formatINR, relativeTime } from '../components/ui';
import { ContextBar } from '../components/Shell';

export function ReportsScreen() {
  const [reports, setReports] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setReports(await api.listReports());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const doc = await api.generateReport({ period_days: 30 });
      setSelected(doc);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const open = async (id) => {
    try {
      setSelected(await api.getReport(id));
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (id) => {
    await api.deleteReport(id);
    if (selected?.id === id) setSelected(null);
    refresh();
  };

  if (selected) {
    return <ReportView doc={selected} onBack={() => setSelected(null)} />;
  }

  return (
    <>
      <ContextBar
        title="Reports"
        subtitle="Point-in-time account read-outs you can download and circulate"
        actions={
          <Button size="sm" icon="add_chart" onClick={generate} disabled={generating}>
            {generating ? 'Generating…' : 'Generate report'}
          </Button>
        }
      />
      <div className="p-4 sm:p-7 max-w-[1100px]">

      {error && <ErrorNote message={error} />}

      {loading ? (
        <div className="flex justify-center py-16 text-primary">
          <Spinner className="w-6 h-6" />
        </div>
      ) : reports.length === 0 ? (
        <EmptyState
          icon="lab_profile"
          title="No reports yet"
          body="Generate one to capture the current state of the account as a shareable document."
          action={
            <Button icon="add_chart" onClick={generate} disabled={generating}>
              Generate the first report
            </Button>
          }
        />
      ) : (
        <ul className="space-y-2">
          {reports.map((report) => (
            <li key={report.id}>
              <div className="card p-4 flex items-center gap-4 hover:border-primary/40 transition-colors">
                <span className="w-10 h-10 rounded-lg bg-primary-fixed text-on-primary-fixed flex items-center justify-center shrink-0">
                  <Icon name="lab_profile" size={20} />
                </span>
                <button onClick={() => open(report.id)} className="flex-1 text-left min-w-0 focus-ring rounded">
                  <p className="font-headline text-body-md font-semibold text-on-surface truncate">
                    {report.title}
                  </p>
                  <p className="text-body-sm text-outline">
                    {relativeTime(report.created_at)} · last {report.period_days} days
                  </p>
                </button>
                <Chip label={report.data_source} />
                <a
                  href={api.reportHtmlUrl(report.id)}
                  title="Download as HTML"
                  className="p-2 rounded-lg text-on-surface-variant hover:bg-surface-container-low focus-ring"
                >
                  <Icon name="download" size={18} />
                </a>
                <button
                  onClick={() => remove(report.id)}
                  title="Delete report"
                  className="p-2 rounded-lg text-outline hover:text-error hover:bg-error-container/40 focus-ring"
                >
                  <Icon name="delete" size={18} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      </div>
    </>
  );
}

function ReportView({ doc, onBack }) {
  const kpis = doc.account_kpis || {};
  const plan = doc.budget_plan || {};

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-container-padding py-6">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-body-sm text-on-surface-variant hover:text-primary mb-4 focus-ring rounded"
      >
        <Icon name="arrow_back" size={16} /> All reports
      </button>

      <header className="mb-6">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <Chip label={doc.data_source} />
          <span className="rail-label">
            Generated {new Date(doc.generated_at).toLocaleString('en-IN')} · last {doc.period_days} days
          </span>
        </div>
        <h1 className="font-headline text-headline-xl text-on-surface">{doc.title}</h1>
        <p className="text-body-sm text-on-surface-variant mt-1">Objective: {doc.objective}</p>
        <div className="flex flex-wrap gap-2 mt-4">
          <a
            href={api.reportHtmlUrl(doc.id)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary text-on-primary px-4 py-2 text-body-sm font-headline font-semibold hover:bg-on-primary-fixed-variant transition-colors focus-ring"
          >
            <Icon name="download" size={17} /> Download report (HTML)
          </a>
          <a
            href={api.reportMarkdownUrl(doc.id)}
            className="inline-flex items-center gap-2 rounded-lg border border-outline-variant/50 bg-surface-container-lowest px-4 py-2 text-body-sm font-headline font-semibold text-on-surface hover:bg-surface-container-low transition-colors focus-ring"
          >
            <Icon name="description" size={17} /> Markdown
          </a>
          <a
            href={api.reportPreviewUrl(doc.id)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-outline-variant/50 bg-surface-container-lowest px-4 py-2 text-body-sm font-headline font-semibold text-on-surface hover:bg-surface-container-low transition-colors focus-ring"
          >
            <Icon name="open_in_new" size={17} /> Print view
          </a>
        </div>
      </header>

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <Kpi label="Total spend" value={formatINR(kpis.total_spend_inr)} />
        <Kpi label="Blended ROAS" value={`${kpis.blended_roas ?? 0}x`} />
        <Kpi label="Blended CPA" value={formatINR(kpis.blended_cpa_inr)} />
        <Kpi label="Conversions" value={formatCompact(kpis.total_conversions)} />
      </section>

      {doc.executive_summary && (
        <Section title="Executive summary">
          <p className="card p-4 text-body-md text-on-surface-variant leading-relaxed">
            {doc.executive_summary}
          </p>
        </Section>
      )}

      {doc.key_takeaways?.length > 0 && (
        <Section title="Key takeaways">
          <ul className="card p-4 space-y-2.5">
            {doc.key_takeaways.map((item, index) => (
              <li key={index} className="flex gap-2.5 text-body-sm text-on-surface-variant">
                <Icon name="lightbulb" size={16} className="text-primary shrink-0 mt-0.5" fill />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {doc.campaigns?.length > 0 && (
        <Section title="Campaign performance">
          <div className="card overflow-hidden overflow-x-auto">
            <table className="w-full text-body-sm">
              <thead className="bg-surface-container-low border-b border-outline-variant/40">
                <tr>
                  {['Campaign', 'Platform', 'Spend', 'ROAS', 'CPA', 'CTR', 'Score', 'Verdict'].map(
                    (heading, index) => (
                      <th
                        key={heading}
                        className={`px-4 py-2.5 rail-label ${index > 1 ? 'text-right' : 'text-left'}`}
                      >
                        {heading}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {doc.campaigns.map((campaign) => (
                  <tr
                    key={campaign.campaign_id}
                    className="border-b border-outline-variant/25 last:border-0"
                  >
                    <td className="px-4 py-2.5 text-on-surface font-medium">{campaign.campaign_name}</td>
                    <td className="px-4 py-2.5 text-on-surface-variant">{platformLabel(campaign.platform)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{formatINR(campaign.spend_inr)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{campaign.roas}x</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{formatINR(campaign.cpa_inr)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{campaign.ctr}%</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{campaign.score}</td>
                    <td className="px-4 py-2.5 text-right">
                      <Chip label={campaign.status_tag} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {doc.what_works?.length > 0 && (
        <BulletSection title="What's working" items={doc.what_works} icon="check_circle" tone="text-green-600" />
      )}
      {doc.decay_signals?.length > 0 && (
        <BulletSection title="Decay signals" items={doc.decay_signals} icon="warning" tone="text-amber-600" />
      )}

      {plan.shifts?.length > 0 && (
        <Section title="Budget reallocation plan">
          <div className="card overflow-hidden overflow-x-auto">
            <table className="w-full text-body-sm">
              <thead className="bg-surface-container-low border-b border-outline-variant/40">
                <tr>
                  {['Campaign', 'Current', 'Proposed', 'Change', 'Rationale'].map((heading, index) => (
                    <th
                      key={heading}
                      className={`px-4 py-2.5 rail-label ${index > 0 && index < 4 ? 'text-right' : 'text-left'}`}
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {plan.shifts.map((shift) => (
                  <tr key={shift.campaign_id} className="border-b border-outline-variant/25 last:border-0">
                    <td className="px-4 py-2.5 text-on-surface font-medium">{shift.campaign_name}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {formatINR(shift.current_daily_budget_inr)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {formatINR(shift.proposed_daily_budget_inr)}
                    </td>
                    <td
                      className={`px-4 py-2.5 text-right tabular-nums font-medium ${
                        shift.shift_percentage >= 0 ? 'text-green-600' : 'text-error'
                      }`}
                    >
                      {shift.shift_percentage >= 0 ? '+' : ''}
                      {shift.shift_percentage}%
                    </td>
                    <td className="px-4 py-2.5 text-on-surface-variant">{shift.rationale}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-surface-container-low font-semibold">
                  <td className="px-4 py-2.5">Total</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">
                    {formatINR(plan.total_current_inr)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">
                    {formatINR(plan.total_proposed_inr)}
                  </td>
                  <td className="px-4 py-2.5 text-right" colSpan={2}>
                    <Chip label={plan.is_conserved ? 'Conserved' : 'Review'} />
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Section>
      )}

      {doc.strategic_advice && (
        <Section title="Strategic advice">
          <p className="card p-4 text-body-md text-on-surface-variant leading-relaxed">
            {doc.strategic_advice}
          </p>
        </Section>
      )}

      <p className="text-body-sm text-outline border-t border-outline-variant/30 pt-4 mt-8">
        Generated by HELM. Every budget change still requires human approval before dispatch.
      </p>
    </div>
  );
}

function Kpi({ label, value }) {
  return (
    <div className="card p-4">
      <p className="rail-label mb-1.5">{label}</p>
      <p className="font-headline text-headline-lg text-on-surface tabular-nums">{value}</p>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="mb-6">
      <h2 className="font-headline text-headline-md text-on-surface mb-2.5">{title}</h2>
      {children}
    </section>
  );
}

function BulletSection({ title, items, icon, tone }) {
  return (
    <Section title={title}>
      <ul className="card p-4 space-y-2.5">
        {items.map((item, index) => (
          <li key={index} className="flex gap-2.5 text-body-sm text-on-surface-variant leading-relaxed">
            <Icon name={icon} size={16} className={`${tone} shrink-0 mt-0.5`} fill />
            {item}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function ErrorNote({ message }) {
  return (
    <div className="rounded-xl border border-error/30 bg-error-container p-3 mb-4 flex gap-2 text-body-sm text-on-error-container">
      <Icon name="error" size={18} className="text-error shrink-0" fill />
      {message}
    </div>
  );
}

function platformLabel(platform) {
  return (
    {
      google_ads: 'Google Ads',
      meta_ads: 'Meta Ads',
      tiktok_ads: 'TikTok Ads',
      linkedin_ads: 'LinkedIn Ads',
      byod: 'Imported',
    }[platform] || platform
  );
}
