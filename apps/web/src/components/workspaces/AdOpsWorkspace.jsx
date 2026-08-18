import React, { useState } from 'react';
import { useHelmStore } from '../../context/HelmStore';
import {
  Database,
  RefreshCw,
  Upload,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  Layers,
  BarChart3,
  ArrowUpRight,
  ShieldAlert,
  PlayCircle,
  HelpCircle,
} from 'lucide-react';

export function AdOpsWorkspace() {
  const {
    syntheticSnapshot,
    generateSyntheticScenario,
    currentRunState,
    startMission,
    setActiveTab,
    isOrchestrating,
  } = useHelmStore();

  const [scenario, setScenario] = useState('growth_and_fatigue');
  const [isGenerating, setIsGenerating] = useState(false);
  const [byodCsv, setByodCsv] = useState('');
  const [showByod, setShowByod] = useState(false);

  const analystReport = currentRunState?.agent_reports?.analyst;
  const campaigns =
    syntheticSnapshot?.campaigns && syntheticSnapshot.campaigns.length > 0
      ? syntheticSnapshot.campaigns
      : analystReport?.per_campaign || [];

  const kpis = analystReport?.account_kpis || {
    total_spend_inr: syntheticSnapshot?.total_spend_inr || 0,
    blended_roas: syntheticSnapshot?.blended_roas || 0,
    total_conversions: campaigns.reduce((acc, c) => acc + (c.conversions || 0), 0),
    blended_cpa_inr:
      syntheticSnapshot?.total_spend_inr && campaigns.reduce((acc, c) => acc + (c.conversions || 0), 0) > 0
        ? Math.round(
            syntheticSnapshot.total_spend_inr /
              campaigns.reduce((acc, c) => acc + (c.conversions || 0), 0)
          )
        : 0,
  };

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

  const handleLaunchAnalysis = () => {
    startMission('Analyze campaign performance, prune fatigued assets, and scale top winners.');
    setActiveTab('governor');
  };

  const topPerformer = campaigns.find((c) => (c.roas || 0) >= 3.0) || campaigns[0];
  const fatiguedCampaign = campaigns.find((c) => c.campaign_id?.includes('fatigue') || (c.score && c.score < 40)) || campaigns[2];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top 4 KPI Metric Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1rem',
        }}
      >
        {/* KPI 1: Total Spend */}
        <div className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span className="lbl" style={{ fontSize: '0.75rem' }}>30-Day Total Spend</span>
            <span className="badge badge-blue">ACCOUNT</span>
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
            ₹{Math.round(kpis.total_spend_inr || 0).toLocaleString()}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
            Across {campaigns.length} active campaigns
          </div>
        </div>

        {/* KPI 2: Blended ROAS */}
        <div className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span className="lbl" style={{ fontSize: '0.75rem' }}>Blended Return on Ad Spend</span>
            <span className="badge badge-emerald">ROAS</span>
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--accent-emerald)' }}>
            {(kpis.blended_roas || 0).toFixed(1)}x
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-green)', marginTop: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
            <ArrowUpRight style={{ width: 14, height: 14 }} /> Above target benchmark (2.0x)
          </div>
        </div>

        {/* KPI 3: Total Conversions & CPA */}
        <div className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span className="lbl" style={{ fontSize: '0.75rem' }}>Conversions &amp; Avg CPA</span>
            <span className="badge badge-blue">CPA</span>
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
            {kpis.total_conversions?.toLocaleString() || 0}
            <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)', fontWeight: 500, marginLeft: '0.4rem' }}>
              (₹{Math.round(kpis.blended_cpa_inr || 0)} CPA)
            </span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
            Average acquisition cost per conversion
          </div>
        </div>

        {/* KPI 4: Top Winning Angle */}
        <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid var(--primary-blue)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span className="lbl" style={{ fontSize: '0.75rem' }}>Top Converting Angle</span>
            <span className="badge badge-emerald">WINNER</span>
          </div>
          <div style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--primary-blue)', lineHeight: 1.3 }}>
            {topPerformer?.campaign_name || topPerformer?.name || 'High-Intent Search'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-green)', marginTop: '0.35rem', fontWeight: 600 }}>
            {topPerformer?.roas || 3.4}x ROAS · Ready to scale
          </div>
        </div>
      </div>

      {/* Main Content Grid: Dataset Generator & Campaign Performance Table */}
      <div className="workspace-grid">
        {/* Left Column: Data Synthesizer Control */}
        <div className="card">
          <div className="panel-header">
            <div>
              <h3 className="panel-heading" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Database style={{ width: 16, height: 16 }} className="text-blue-600" /> Marketing Data Control
              </h3>
              <p className="panel-desc" style={{ marginTop: '0.2rem' }}>
                Switch between simulated multi-channel scenarios with realistic CTR and CPA variances.
              </p>
            </div>
          </div>

          <div className="form-group" style={{ marginTop: '0.75rem' }}>
            <label className="form-label">Select Campaign Scenario Preset</label>
            <select
              className="form-select"
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            >
              <option value="growth_and_fatigue">1. Search Growth + Meta Fatigue (Default)</option>
              <option value="scale_winner">2. High-ROAS SIP Winner Scaling</option>
              <option value="sebi_risk_scenario">3. SEBI Compliance Risk &amp; Loopback</option>
              <option value="multi_channel_mix">4. Multi-Channel Balanced Mix</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '1rem' }}>
            <button
              type="button"
              disabled={isGenerating}
              onClick={handleGenerate}
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center' }}
            >
              <RefreshCw
                style={{ width: 15, height: 15 }}
                className={isGenerating ? 'animate-spin' : ''}
              />
              {isGenerating ? 'Generating SQLite Data...' : 'Seed This Dataset into SQLite'}
            </button>

            <button
              type="button"
              disabled={isOrchestrating}
              onClick={handleLaunchAnalysis}
              className="btn btn-secondary"
              style={{ width: '100%', justifyContent: 'center', marginTop: '0.25rem' }}
            >
              <PlayCircle style={{ width: 15, height: 15 }} className="text-blue-600" />
              Run Governor Analysis on This Data
            </button>
          </div>

          {/* Collapsible BYOD CSV Importer */}
          <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
            <button
              type="button"
              onClick={() => setShowByod(!showByod)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: '0.8125rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
              }}
            >
              <Upload style={{ width: 14, height: 14 }} />
              {showByod ? 'Hide Custom CSV Importer' : 'Upload Custom CSV (BYOD)'}
            </button>

            {showByod && (
              <div style={{ marginTop: '0.75rem' }}>
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
                  <Upload style={{ width: 14, height: 14 }} /> Parse CSV Snapshot
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Campaign Performance Table */}
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Live Campaign Performance Metrics</h3>
              <p className="card-sub" style={{ fontSize: '0.8125rem' }}>
                Snapshot of active campaigns across Google Ads and Meta Ads
              </p>
            </div>
            <span className="badge badge-blue">
              {syntheticSnapshot ? 'SQLITE LIVE' : 'SYNCING'}
            </span>
          </div>

          {campaigns.length === 0 ? (
            <div className="empty-state-hint" style={{ padding: '2rem 1rem', textAlign: 'center' }}>
              Loading campaigns from SQLite store...
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="metric-table">
                <thead>
                  <tr>
                    <th>Campaign Name</th>
                    <th>Platform</th>
                    <th>Spend</th>
                    <th>ROAS</th>
                    <th>CPA</th>
                    <th>CTR</th>
                    <th>Health Score</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((c) => {
                    const roasVal = c.roas || 0;
                    const scoreVal = c.score || ((roasVal >= 3.0) ? 88 : (roasVal < 1.5) ? 35 : 72);
                    const isWinner = scoreVal >= 70;
                    const isFatigued = scoreVal < 40;
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
                          <span className={`badge ${c.platform === 'google_ads' ? 'badge-blue' : 'badge-purple'}`}>
                            {c.platform === 'google_ads' ? 'Google' : 'Meta'}
                          </span>
                        </td>
                        <td>₹{Math.round(c.spend_inr || c.spend || 0).toLocaleString()}</td>
                        <td>
                          <strong
                            className={
                              roasVal >= 3.0 ? 'text-green' : roasVal < 2.0 ? 'text-red' : 'text-blue'
                            }
                          >
                            {roasVal.toFixed(1)}x
                          </strong>
                        </td>
                        <td>₹{Math.round(c.cpa_inr || c.cpa || 0)}</td>
                        <td>{c.ctr}%</td>
                        <td>
                          <span
                            className={`badge ${
                              isWinner ? 'badge-emerald' : isFatigued ? 'badge-amber' : 'badge-blue'
                            }`}
                          >
                            {scoreVal}/100 {isWinner ? '★ WINNER' : isFatigued ? '⚠️ FATIGUED' : 'STABLE'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* AI Executive Insights & Diagnosis Panel */}
      <div className="card" style={{ padding: '1.5rem', background: '#ffffff' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
          <Sparkles className="text-blue-600" style={{ width: 20, height: 20 }} />
          <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)' }}>
            AI Performance Diagnosis &amp; Strategic Insights
          </h3>
          <span className="badge badge-purple" style={{ marginLeft: 'auto' }}>
            GEMINI POWERED
          </span>
        </div>

        {analystReport?.executive_summary ? (
          <div style={{ marginBottom: '1.25rem', padding: '1rem 1.25rem', background: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <p style={{ fontSize: '0.9375rem', lineHeight: 1.6, color: '#1e293b' }}>
              {analystReport.executive_summary}
            </p>
          </div>
        ) : (
          <div style={{ marginBottom: '1.25rem', padding: '1rem 1.25rem', background: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <p style={{ fontSize: '0.875rem', lineHeight: 1.6, color: 'var(--text-muted)' }}>
              Click <strong>"Run Governor Analysis"</strong> to generate a full AI executive diagnosis and budget reallocation plan for this dataset.
            </p>
          </div>
        )}

        {/* 3 Insight Blocks */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '1rem',
          }}
        >
          {/* Winning Angles */}
          <div className="card" style={{ padding: '1rem 1.25rem', background: 'var(--accent-emerald-light)', border: '1px solid #a7f3d0' }}>
            <h4 className="subheading" style={{ color: '#065f46', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.5rem' }}>
              <CheckCircle2 style={{ width: 16, height: 16 }} /> What Is Working Well
            </h4>
            <ul style={{ fontSize: '0.8125rem', lineHeight: 1.6, listStyle: 'none', color: '#065f46' }}>
              {(analystReport?.what_works && analystReport.what_works.length > 0
                ? analystReport.what_works
                : [
                    'Mutual Fund High-Intent Search delivers 3.4x ROAS with low ₹107 CPA.',
                    'SIP Growth Video Retargeting is maintaining steady 2.1x ROAS.',
                  ]
              ).map((w, i) => (
                <li key={i} style={{ marginBottom: '0.35rem' }}>
                  ✓ {w}
                </li>
              ))}
            </ul>
          </div>

          {/* Decay / Fatigue Signals */}
          <div className="card" style={{ padding: '1rem 1.25rem', background: 'var(--accent-rose-light)', border: '1px solid #fecaca' }}>
            <h4 className="subheading" style={{ color: '#991b1b', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.5rem' }}>
              <AlertTriangle style={{ width: 16, height: 16 }} /> Fatigue &amp; Decay Signals
            </h4>
            <ul style={{ fontSize: '0.8125rem', lineHeight: 1.6, listStyle: 'none', color: '#991b1b' }}>
              {(analystReport?.decay_signals && analystReport.decay_signals.length > 0
                ? analystReport.decay_signals
                : [
                    'Gold ETF Broad Audience is decaying: CTR dropped 35%, CPA surged from ₹168 to ₹315.',
                    'Creative fatigue detected: audience exhaustion on broad display assets.',
                  ]
              ).map((d, i) => (
                <li key={i} style={{ marginBottom: '0.35rem' }}>
                  ⚠️ {d}
                </li>
              ))}
            </ul>
          </div>

          {/* Growth & Optimization Advice */}
          <div className="card" style={{ padding: '1rem 1.25rem', background: 'var(--primary-blue-light)', border: '1px solid #bfdbfe' }}>
            <h4 className="subheading" style={{ color: '#1e40af', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.5rem' }}>
              <TrendingUp style={{ width: 16, height: 16 }} /> Recommended Actions
            </h4>
            <ul style={{ fontSize: '0.8125rem', lineHeight: 1.6, listStyle: 'none', color: '#1e40af' }}>
              <li style={{ marginBottom: '0.35rem' }}>
                📈 Scale budget on High-Intent Search by +20% (₹45,000 → ₹54,000/day).
              </li>
              <li style={{ marginBottom: '0.35rem' }}>
                📉 Cut spend on fatigued Gold ETF by -20% (₹30,000 → ₹24,000/day).
              </li>
              <li>
                🎨 Launch 1 fresh video creative to test incremental audience headroom.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

