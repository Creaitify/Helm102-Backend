/**
 * Data Sources: shape the synthetic dataset, upload real Excel/CSV/JSON files, or import via URL.
 *
 * This is what makes the demo path honest — you pick a scenario or supply real data,
 * the backend ingests and normalizes it, and every agent immediately reasons over the new numbers.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { useHelm } from '../store';
import { Button, Chip, Icon, Spinner, formatCompact, formatINR } from '../components/ui';
import { ContextBar } from '../components/Shell';

export function DataSourcesScreen() {
  const { refreshOverview } = useHelm();
  const [scenarios, setScenarios] = useState([]);
  const [snapshot, setSnapshot] = useState(null);
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(null);
  const [notice, setNotice] = useState(null);
  const [activeMode, setActiveMode] = useState('upload'); // 'upload' | 'url' | 'csv' | 'scenarios'

  // CSV paste state
  const [csv, setCsv] = useState('');
  const [csvResult, setCsvResult] = useState(null);

  // URL ingestion state
  const [byodUrl, setByodUrl] = useState('');

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

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setBusy('upload');
    setNotice(null);
    try {
      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          let fileContent;
          if (
            file.name.endsWith('.xlsx') ||
            file.name.endsWith('.xls') ||
            file.name.endsWith('.pdf')
          ) {
            const binary = e.target.result;
            fileContent = btoa(
              new Uint8Array(binary).reduce((data, byte) => data + String.fromCharCode(byte), ''),
            );
          } else {
            fileContent = e.target.result;
          }

          const res = await api.uploadByod(fileContent, file.name, true);
          setNotice({
            tone: 'success',
            text: `Successfully ingested "${file.name}" with ${res.campaign_count} campaigns (${formatINR(res.total_spend_inr)} spend). Active across all agents!`,
          });
          await loadSnapshot();
          refreshOverview();
        } catch (err) {
          setNotice({ tone: 'error', text: err.message });
        } finally {
          setBusy(null);
        }
      };

      if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
        reader.readAsArrayBuffer(file);
      } else {
        reader.readAsText(file);
      }
    } catch (err) {
      setNotice({ tone: 'error', text: err.message });
      setBusy(null);
    }
  };

  const handleUrlIngest = async () => {
    if (!byodUrl.trim()) return;
    setBusy('url');
    setNotice(null);
    try {
      const res = await api.ingestByodUrl(byodUrl.trim(), true);
      setNotice({
        tone: 'success',
        text: `Fetched and ingested ${res.campaign_count} campaigns from URL (${formatINR(res.total_spend_inr)} spend).`,
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
      const res = await api.parseByod(csv, true);
      setCsvResult(res);
      setNotice({
        tone: 'success',
        text: `Parsed and activated ${res.campaign_count} campaigns (${formatINR(res.total_spend_inr)} spend).`,
      });
      await loadSnapshot();
      refreshOverview();
    } catch (err) {
      setNotice({ tone: 'error', text: err.message });
    } finally {
      setBusy(null);
    }
  };

  const clearCustomData = async () => {
    setBusy('clear');
    setNotice(null);
    try {
      await api.clearByod();
      setNotice({
        tone: 'success',
        text: 'Custom dataset cleared. Restored SQLite synthetic dataset.',
      });
      setCsvResult(null);
      await loadSnapshot();
      refreshOverview();
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
      <div className="p-4 sm:p-7 max-w-[1100px] space-y-6">
        {notice && (
          <div
            className={`rounded-xl p-3 flex gap-2 text-body-sm ${
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
        <section className="card p-5">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div>
              <h2 className="font-headline text-headline-md text-on-surface">Current active dataset</h2>
              <p className="text-body-sm text-on-surface-variant">
                Live campaign facts used by Analyst, Governor, Creative, and Media Buyer.
              </p>
            </div>
            {snapshot?.source === 'byod' && (
              <Button
                variant="secondary"
                size="sm"
                icon="delete_sweep"
                onClick={clearCustomData}
                disabled={busy === 'clear'}
              >
                {busy === 'clear' ? 'Restoring…' : 'Restore Synthetic Baseline'}
              </Button>
            )}
          </div>

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

        {/* Ingestion modes navigation */}
        <section className="card p-5">
          <div className="flex flex-wrap border-b border-outline-variant/30 gap-4 mb-4">
            {[
              { id: 'upload', label: 'File Upload (CSV / XLSX / JSON / PDF)', icon: 'upload_file' },
              { id: 'url', label: 'Remote URL Ingestion', icon: 'link' },
              { id: 'csv', label: 'Paste Raw CSV', icon: 'code' },
              { id: 'scenarios', label: 'Synthetic Scenarios', icon: 'auto_mode' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveMode(tab.id)}
                className={`flex items-center gap-2 pb-3 text-body-sm font-semibold border-b-2 transition-colors ${
                  activeMode === tab.id
                    ? 'border-primary text-primary'
                    : 'border-transparent text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <Icon name={tab.icon} size={18} fill={activeMode === tab.id} />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Mode 1: File Upload */}
          {activeMode === 'upload' && (
            <div className="space-y-3">
              <p className="text-body-sm text-on-surface-variant">
                Upload your campaign data workbook (multi-sheet <code>.xlsx</code>), CSV (<code>.csv</code>), JSON, or PDF report/brief (<code>.pdf</code>). Column aliases, missing metrics (spend, ROAS, CPA, CTR), and channel types will be auto-derived.
              </p>
              <label className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-outline-variant/60 rounded-xl bg-surface-container-low/40 hover:bg-surface-container-low transition-colors cursor-pointer">
                <Icon name="cloud_upload" size={36} className="text-primary mb-2" />
                <span className="text-body-md font-semibold text-on-surface">Click to select or drag & drop</span>
                <span className="text-body-sm text-outline mt-0.5">Supports .csv, .xlsx, .xls, .json, and .pdf files</span>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.json,.pdf,text/csv,application/json,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
                  onChange={handleFileUpload}
                  disabled={busy === 'upload'}
                  className="hidden"
                />
              </label>
              {busy === 'upload' && (
                <div className="flex items-center gap-2 text-body-sm text-primary">
                  <Spinner className="w-4 h-4" /> Ingesting and normalizing dataset…
                </div>
              )}
            </div>
          )}

          {/* Mode 2: URL Ingestion */}
          {activeMode === 'url' && (
            <div className="space-y-3">
              <p className="text-body-sm text-on-surface-variant">
                Fetch and ingest campaign data directly from a public URL (HTTP/HTTPS endpoint serving CSV, XLSX, or JSON).
              </p>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={byodUrl}
                  onChange={(e) => setByodUrl(e.target.value)}
                  placeholder="https://example.com/marketing_campaigns.csv"
                  className="flex-1 bg-surface-container-low border border-outline-variant/40 rounded-lg px-3 py-2 text-body-sm focus-ring"
                />
                <Button
                  icon="download"
                  onClick={handleUrlIngest}
                  disabled={!byodUrl.trim() || busy === 'url'}
                >
                  {busy === 'url' ? 'Fetching…' : 'Ingest URL'}
                </Button>
              </div>
            </div>
          )}

          {/* Mode 3: Raw CSV Paste */}
          {activeMode === 'csv' && (
            <div className="space-y-3">
              <p className="text-body-sm text-on-surface-variant">
                Columns: <code>campaign_id, campaign_name, platform, spend_inr, impressions, clicks, conversions, roas, cpa_inr, ctr, status</code>
              </p>
              <textarea
                value={csv}
                onChange={(event) => setCsv(event.target.value)}
                rows={6}
                placeholder="campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status&#10;cmp_01,Search Intent,google_ads,45000,125000,8400,420,3.4,107.14,6.72,ENABLED"
                className="w-full font-mono text-[11px] bg-surface-container-low border border-outline-variant/40 rounded-lg p-3 resize-y focus-ring"
              />
              <div className="flex flex-wrap gap-2">
                <Button icon="upload_file" onClick={parseCsv} disabled={!csv.trim() || busy === 'csv'}>
                  {busy === 'csv' ? 'Activating…' : 'Parse & Activate'}
                </Button>
                <Button variant="secondary" icon="description" onClick={loadSample}>
                  Load sample dataset
                </Button>
              </div>
            </div>
          )}

          {/* Mode 4: Synthetic Scenario Generator */}
          {activeMode === 'scenarios' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-body-sm text-on-surface-variant">
                  Generate coherent marketing scenarios into SQLite with simulated CTR decay, ad fatigue, and ROAS shifts.
                </p>
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
                  <article key={scenario.id} className="p-4 rounded-xl border border-outline-variant/40 bg-surface-container-low/40 flex flex-col">
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
