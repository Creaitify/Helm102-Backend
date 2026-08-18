import React, { useState } from 'react';
import { useHelmStore } from '../../context/HelmStore';
import { Database, RefreshCw, Upload, TrendingUp, AlertCircle, CheckCircle } from 'lucide-react';

export function AdOpsWorkspace() {
  const {
    syntheticSnapshot,
    generateSyntheticScenario,
    currentRunState,
  } = useHelmStore();
  const [scenario, setScenario] = useState('growth_and_fatigue');
  const [isGenerating, setIsGenerating] = useState(false);
  const [byodCsv, setByodCsv] = useState('');

  const analystReport = currentRunState?.agent_reports?.analyst;
  const campaigns =
    analystReport?.per_campaign || syntheticSnapshot?.campaigns || [];

  const handleGenerate = async () => {
    setIsGenerating(true);
    await generateSyntheticScenario(scenario, 60);
    setIsGenerating(false);
  };

  const handleByodParse = async () => {
    if (!byodCsv.trim()) return;
    try {
      const res = await fetch('/api/byod/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ csv_content: byodCsv }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      alert(`BYOD Parse Success: ${data.campaign_count} campaigns loaded.`);
    } catch (err) {
      alert(`BYOD parse error: ${err.message}`);
    }
  };

  return (
    <div className="workspace-grid">
      {/* Left: SQLite Synthetic Engine & BYOD Importer */}
      <div className="card">
        <div className="panel-header">
          <h3 className="panel-heading">SQLite Synthetic Engine</h3>
          <span className="badge badge-blue">SQLite DB</span>
        </div>
        <p className="panel-desc">
          Generate coherent multi-channel marketing campaigns with 30-60 day variances (CTR decay, ROAS shifts, fatigue signals).
        </p>

        <div className="form-group">
          <label className="form-label">Data Scenario Preset</label>
          <select
            className="form-select"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          >
            <option value="growth_and_fatigue">Search Growth + Meta Fatigue (Default)</option>
            <option value="scale_winner">High-ROAS SIP Winner Scaling</option>
            <option value="sebi_risk_scenario">SEBI Compliance Risk &amp; Loopback</option>
            <option value="multi_channel_mix">Multi-Channel Balanced Mix</option>
          </select>
        </div>

        <button
          type="button"
          disabled={isGenerating}
          onClick={handleGenerate}
          className="btn btn-primary btn-sm"
          style={{ width: '100%', marginBottom: '1.5rem' }}
        >
          <RefreshCw
            style={{ width: 14, height: 14 }}
            className={isGenerating ? 'animate-spin' : ''}
          />
          {isGenerating ? 'Generating SQLite Data...' : 'Generate & Seed SQLite Data'}
        </button>

        <h4 className="subheading" style={{ marginTop: '1rem' }}>BYOD CSV Importer</h4>
        <textarea
          className="form-textarea"
          rows={3}
          value={byodCsv}
          onChange={(e) => setByodCsv(e.target.value)}
          placeholder="campaign_id,campaign_name,platform,spend_inr,impressions,clicks,conversions,roas,cpa_inr,ctr,status"
        />
        <button
          type="button"
          onClick={handleByodParse}
          className="btn btn-secondary btn-sm"
          style={{ width: '100%', marginTop: '0.5rem' }}
        >
          <Upload style={{ width: 14, height: 14 }} /> Upload Custom CSV
        </button>
      </div>

      {/* Right: Ingested Multi-Channel Campaign Snapshot */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Ingested Multi-Channel Campaign Metrics</h3>
          <span className="badge badge-blue">
            {analystReport ? 'GOVERNOR INGESTED' : 'SQLITE SNAPSHOT'}
          </span>
        </div>

        {campaigns.length === 0 ? (
          <div className="empty-state-hint">Loading campaigns from SQLite store...</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="metric-table">
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Platform</th>
                  <th>Spend</th>
                  <th>ROAS</th>
                  <th>CPA</th>
                  <th>CTR</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => {
                  const roasVal = c.roas || 0;
                  const scoreVal = c.score || 80;
                  return (
                    <tr key={c.campaign_id}>
                      <td>
                        <strong>{c.campaign_name || c.name}</strong>
                        <br />
                        <span className="mono text-muted" style={{ fontSize: '0.75rem' }}>
                          {c.campaign_id}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-blue">{c.platform}</span>
                      </td>
                      <td>₹{Number(c.spend_inr || c.spend || 0).toLocaleString()}</td>
                      <td>
                        <strong
                          className={
                            roasVal >= 3.0 ? 'text-green' : roasVal < 2.0 ? 'text-red' : 'text-blue'
                          }
                        >
                          {roasVal}x
                        </strong>
                      </td>
                      <td>₹{Math.round(c.cpa_inr || c.cpa || 0)}</td>
                      <td>{c.ctr}%</td>
                      <td>
                        <span
                          className={`badge ${scoreVal >= 70 ? 'badge-emerald' : 'badge-amber'}`}
                        >
                          {scoreVal}/100
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Analytics Insights */}
        {analystReport && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '1rem',
              marginTop: '1.5rem',
            }}
          >
            <div className="card" style={{ padding: '1rem' }}>
              <h4 className="subheading" style={{ color: 'var(--primary-blue)' }}>
                Trend Analysis
              </h4>
              <ul style={{ fontSize: '0.8125rem', lineHeight: 1.6, listStyle: 'none' }}>
                {(analystReport.trends || []).map((t, i) => (
                  <li key={i}>📈 {t}</li>
                ))}
              </ul>
            </div>
            <div className="card" style={{ padding: '1rem' }}>
              <h4 className="subheading" style={{ color: 'var(--accent-emerald)' }}>
                Winning Angles
              </h4>
              <ul style={{ fontSize: '0.8125rem', lineHeight: 1.6, listStyle: 'none' }}>
                {(analystReport.what_works || []).map((w, i) => (
                  <li key={i} className="text-green">
                    ✅ {w}
                  </li>
                ))}
              </ul>
            </div>
            <div className="card" style={{ padding: '1rem' }}>
              <h4 className="subheading" style={{ color: 'var(--accent-rose)' }}>
                Decay Signals
              </h4>
              <ul style={{ fontSize: '0.8125rem', lineHeight: 1.6, listStyle: 'none' }}>
                {(analystReport.decay_signals || []).map((d, i) => (
                  <li key={i} className="text-red">
                    ⚠️ {d}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
