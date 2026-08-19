/**
 * Data Sources: shape the synthetic dataset, or import your own CSV.
 *
 * This is what makes the demo path honest — you pick a scenario, the backend
 * regenerates a coherent multi-channel dataset, and every agent immediately
 * reasons over the new numbers.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { useHelm } from '../store';
import { Button, Chip, Icon, Spinner, formatCompact, formatINR } from '../components/ui';
import { ContextBar } from '../components/Shell';

export function DataSourcesScreen() {
  const { refreshOverview, health } = useHelm();
  const [scenarios, setScenarios] = useState([]);
  const [snapshot, setSnapshot] = useState(null);
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(null);
  const [notice, setNotice] = useState(null);
  const [csv, setCsv] = useState('');
  const [csvResult, setCsvResult] = useState(null);

  const loadSnapshot = useCallback(async () => {
    try {
      setSnapshot(await api.currentSynthetic());
    } catch (err) {
      setNotice({ tone: 'error', text: err.message });
    }
  }, []);

  useEffect(() => {
    api.syntheticScenarios().then(setScenarios).catch(() => {});
    loadSnapshot();
  }, [loadSnapshot]);

  const generate = async (scenarioId) => {
    setBusy(scenarioId);
    setNotice(null);
    try {
      const result = await api.generateSynthetic(scenarioId, days);
      setNotice({
        tone: 'success',
        text: `Seeded ${result.campaign_count ?? ''} campaigns over ${days} days. Every agent now reads this dataset.`,
      });
      await loadSnapshot();
      refreshOverview();
    } catch (err) {
      setNotice({ tone: 'error', text: err.message });
    } finally {
      setBusy(null);
    }
  };

  const parseCsv = async () => {
    setBusy('csv');
    setCsvResult(null);
    try {
      setCsvResult(await api.parseByod(csv));
    } catch (err) {
      setNotice({ tone: 'error', text: err.message });
    } finally {
      setBusy(null);
    }
  };

  const loadSample = async () => {
    try {
      const sample = await api.byodSample();
      const sheet = Object.values(sample.data)[0];
      if (Array.isArray(sheet) && sheet.length) {
        const headers = Object.keys(sheet[0]);
        setCsv(
          [headers.join(','), ...sheet.map((row) => headers.map((h) => row[h]).join(','))].join('\n'),
        );
      }
    } catch (err) {
      setNotice({ tone: 'error', text: err.message });
    }
  };

  return (
    <>
      <ContextBar title="Data Sources" subtitle="Agents reason over whatever is loaded here" />
      <div className="p-4 sm:p-7 max-w-[1100px]">

      {notice && (
        <div
          className={`rounded-xl p-3 mb-5 flex gap-2 text-body-sm ${
            notice.tone === 'error'
              ? 'border border-error/30 bg-error-container text-on-error-container'
              : 'border border-green-200 bg-green-50 text-green-800'
          }`}
        >
          <Icon name={notice.tone === 'error' ? 'error' : 'check_circle'} size={18} fill />
          {notice.text}
        </div>
      )}

      {/* Current dataset */}
      <section className="card p-5 mb-6">
        <h2 className="font-headline text-headline-md text-on-surface mb-3">Current dataset</h2>
        {!snapshot ? (
          <div className="flex justify-center py-6 text-primary">
            <Spinner className="w-5 h-5" />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
              <Metric label="Campaigns" value={snapshot.campaign_count} />
              <Metric label="Total spend" value={formatINR(snapshot.total_spend_inr)} />
              <Metric label="Blended ROAS" value={`${snapshot.blended_roas}x`} />
              <Metric label="Source" value={snapshot.source} />
            </div>
            <div className="overflow-x-auto -mx-1">
              <table className="w-full text-body-sm">
                <thead className="bg-surface-container-low">
                  <tr>
                    {['Campaign', 'Platform', 'Spend', 'ROAS', 'CPA', 'CTR', 'Status'].map((h, i) => (
                      <th
                        key={h}
                        className={`px-3 py-2 rail-label ${i >= 2 && i <= 5 ? 'text-right' : 'text-left'}`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {snapshot.campaigns.map((campaign) => (
                    <tr
                      key={campaign.campaign_id}
                      className="border-b border-outline-variant/25 last:border-0"
                    >
                      <td className="px-3 py-2 text-on-surface font-medium">{campaign.campaign_name}</td>
                      <td className="px-3 py-2 text-on-surface-variant">
                        {{
                          google_ads: 'Google Ads',
                          meta_ads: 'Meta Ads',
                          tiktok_ads: 'TikTok Ads',
                          linkedin_ads: 'LinkedIn Ads',
                          byod: 'Imported',
                        }[campaign.platform] || campaign.platform}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatINR(campaign.spend_inr)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{campaign.roas}x</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatINR(campaign.cpa_inr)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{campaign.ctr}%</td>
                      <td className="px-3 py-2">
                        <Chip label={campaign.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {snapshot.notes && <p className="text-body-sm text-outline mt-3">{snapshot.notes}</p>}
          </>
        )}
      </section>

      {/* Scenario presets */}
      <section className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h2 className="font-headline text-headline-md text-on-surface">Synthetic scenarios</h2>
          <label className="flex items-center gap-2 text-body-sm text-on-surface-variant">
            Lookback
            <select
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
              className="bg-surface-container-low border border-outline-variant/40 rounded-lg px-2.5 py-1.5 text-body-sm focus-ring"
            >
              {[14, 30, 60, 90].map((option) => (
                <option key={option} value={option}>
                  {option} days
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {scenarios.map((scenario) => (
            <article key={scenario.id} className="card p-4 flex flex-col">
              <h3 className="font-headline text-body-md font-semibold text-on-surface mb-1">
                {scenario.name}
              </h3>
              <p className="text-body-sm text-on-surface-variant leading-relaxed flex-1 mb-3">
                {scenario.description}
              </p>
              <Button
                variant="secondary"
                icon="autorenew"
                size="sm"
                onClick={() => generate(scenario.id)}
                disabled={busy === scenario.id}
                className="self-start"
              >
                {busy === scenario.id ? 'Seeding…' : 'Load this scenario'}
              </Button>
            </article>
          ))}
        </div>
      </section>

      {/* BYOD */}
      <section className="card p-5">
        <h2 className="font-headline text-headline-md text-on-surface mb-1">
          Import your own data (CSV)
        </h2>
        <p className="text-body-sm text-on-surface-variant mb-3">
          Columns: campaign_id, campaign_name, platform, spend_inr, impressions, clicks,
          conversions, roas, cpa_inr, ctr, status
        </p>

        <textarea
          value={csv}
          onChange={(event) => setCsv(event.target.value)}
          rows={6}
          placeholder="campaign_id,campaign_name,platform,spend_inr,…"
          className="w-full font-mono text-[11px] bg-surface-container-low border border-outline-variant/40 rounded-lg p-3 resize-y focus-ring"
        />

        <div className="flex flex-wrap gap-2 mt-3">
          <Button icon="upload_file" onClick={parseCsv} disabled={!csv.trim() || busy === 'csv'}>
            {busy === 'csv' ? 'Parsing…' : 'Parse CSV'}
          </Button>
          <Button variant="secondary" icon="description" onClick={loadSample}>
            Load sample dataset
          </Button>
        </div>

        {csvResult && (
          <div className="mt-4 rounded-lg border border-green-200 bg-green-50 p-3 text-body-sm text-green-800">
            <p className="font-semibold mb-1">
              Parsed {csvResult.campaign_count} campaigns · {formatINR(csvResult.total_spend_inr)}{' '}
              spend · {csvResult.blended_roas}x blended ROAS
            </p>
            <ul className="space-y-0.5">
              {csvResult.campaigns.slice(0, 5).map((campaign) => (
                <li key={campaign.campaign_id} className="font-mono text-[11px]">
                  {campaign.campaign_name} — {formatINR(campaign.spend_inr)} · {campaign.roas}x
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
      </div>
    </>
  );
}

function Metric({ label, value }) {
  return (
    <div className="bg-surface-container-low rounded-lg p-3">
      <p className="rail-label mb-1">{label}</p>
      <p className="font-headline text-headline-md text-on-surface tabular-nums capitalize">
        {formatCompact(value) === String(value) ? value : formatCompact(value)}
      </p>
    </div>
  );
}
