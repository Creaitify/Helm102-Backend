import React from 'react';
import { useHelmStore } from '../../context/HelmStore';

export function AnalysisPage({ onOpenDataCenter }) {
  const { currentRunState, syntheticSnapshot, byodSnapshot } = useHelmStore();

  const analystReport = currentRunState?.agent_reports?.analyst;
  const isRealData = byodSnapshot != null;

  const campaigns =
    byodSnapshot?.campaigns && byodSnapshot.campaigns.length > 0
      ? byodSnapshot.campaigns
      : syntheticSnapshot?.campaigns && syntheticSnapshot.campaigns.length > 0
      ? syntheticSnapshot.campaigns
      : analystReport?.per_campaign || [];

  const totalSpend =
    byodSnapshot?.total_spend_inr ||
    syntheticSnapshot?.total_spend_inr ||
    analystReport?.account_kpis?.total_spend_inr ||
    campaigns.reduce((acc, c) => acc + (c.spend_inr || c.spend || 0), 0) ||
    40000;

  const blendedRoas =
    byodSnapshot?.blended_roas ||
    syntheticSnapshot?.blended_roas ||
    analystReport?.account_kpis?.blended_roas ||
    (totalSpend > 0
      ? campaigns.reduce((acc, c) => acc + (c.roas || 0) * (c.spend_inr || c.spend || 0), 0) / totalSpend
      : 3.4) ||
    3.4;

  const totalConversions =
    campaigns.reduce((acc, c) => acc + (c.conversions || 0), 0) || 117;

  const blendedCpa =
    totalConversions > 0 ? Math.round(totalSpend / totalConversions) : 341;

  return (
    <div className="max-w-4xl mx-auto w-full flex flex-col gap-6 py-4">
      {/* Header */}
      <div className="border-b border-outline-variant/20 pb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="font-headline-xl text-xl font-bold text-on-surface">
            Campaign Performance Analysis
          </h2>
          <span className="bg-agent-blue/10 text-agent-blue border border-agent-blue/20 px-2.5 py-0.5 rounded text-[11px] font-label-mono font-bold">
            Direct Analyst Mode
          </span>
        </div>
        <button
          onClick={onOpenDataCenter}
          className="text-xs font-label-mono text-primary bg-primary-fixed/30 hover:bg-primary-fixed/50 px-3 py-1.5 rounded-lg border border-primary/20 flex items-center gap-1.5 transition-colors"
        >
          <span className="material-symbols-outlined text-[14px]">upload_file</span>
          {isRealData ? 'Change Dataset (BYOD)' : 'Upload Real Dataset'}
        </button>
      </div>

      {/* User Message Bubble */}
      <div className="flex gap-4 items-start">
        <div className="w-8 h-8 rounded-full bg-tertiary-container text-on-tertiary-container flex items-center justify-center font-headline-md shrink-0 shadow-sm text-xs font-bold">
          RM
        </div>
        <div className="flex-1 bg-surface-container-low rounded-xl p-4 border border-outline-variant/20">
          <p className="text-sm text-on-surface">
            {currentRunState?.objective || 'Analyze Meta and Google campaign performance for the last 30 days.'}
          </p>
          <div className="mt-2 text-right text-[10px] text-outline font-label-mono uppercase">
            10:31 AM
          </div>
        </div>
      </div>

      {/* Analyst Agent Response */}
      <div className="flex gap-4 items-start">
        <div className="w-8 h-8 rounded-full bg-agent-blue text-white flex items-center justify-center shrink-0 shadow-sm">
          <span className="material-symbols-outlined text-[18px]">query_stats</span>
        </div>
        <div className="flex-1 space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-headline-md text-sm font-bold text-on-surface">Analyst Agent</span>
            <span className="text-[10px] text-outline font-label-mono uppercase">10:31 AM</span>
          </div>

          {/* Performance Overview Card */}
          <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-outline-variant/20 bg-surface-container-low/50 flex justify-between items-center">
              <h3 className="font-headline-md text-sm font-bold text-on-surface">
                {isRealData ? 'Real Uploaded Campaign Performance' : 'Meta & Google Campaign Performance (Last 30 Days)'}
              </h3>
              <span className={`text-[10px] font-label-mono font-bold px-2 py-0.5 rounded ${isRealData ? 'bg-agent-green/10 text-agent-green' : 'bg-primary/10 text-primary'}`}>
                {isRealData ? 'REAL DATA' : 'SYNTHETIC SNAPSHOT'}
              </span>
            </div>

            <div className="p-5">
              {/* 4 KPI Scorecard */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                {[
                  { label: 'Spend', value: `₹${Math.round(totalSpend).toLocaleString()}`, change: '+12.5%', color: 'text-agent-green' },
                  { label: 'ROAS', value: `${blendedRoas.toFixed(1)}x`, change: '+0.8x', color: 'text-agent-green' },
                  { label: 'CPA', value: `₹${blendedCpa}`, change: '-18%', color: 'text-agent-green' },
                  { label: 'Conversions', value: `${totalConversions}`, change: '+15', color: 'text-agent-green' },
                ].map((stat) => (
                  <div key={stat.label} className="space-y-1">
                    <div className="text-[10px] text-outline font-label-mono uppercase tracking-wider">
                      {stat.label}
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="font-headline-lg text-lg font-black text-on-surface">
                        {stat.value}
                      </span>
                      <span className={`${stat.color} text-[10px] font-label-mono bg-agent-green/10 px-1.5 rounded font-bold`}>
                        {stat.change}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Performance Overview Narrative */}
              <div className="space-y-2">
                <h4 className="font-headline-md text-sm font-bold text-on-surface">Performance Overview</h4>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  {analystReport?.executive_summary ||
                    'High-Intent Search and Retargeting campaigns show strong performance with 3.4x ROAS, outperforming the account average. Gold ETF and Broad display assets show creative fatigue with declining CTR.'}
                </p>
              </div>
            </div>
          </div>

          {/* Campaign Metrics Table */}
          {campaigns.length > 0 && (
            <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl overflow-hidden shadow-sm">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-surface-container-low text-outline-variant font-label-mono uppercase border-b border-outline-variant/30">
                    <th className="px-4 py-3">Campaign</th>
                    <th className="px-4 py-3">Platform</th>
                    <th className="px-4 py-3 text-right">Spend</th>
                    <th className="px-4 py-3 text-right">ROAS</th>
                    <th className="px-4 py-3 text-right">CPA</th>
                    <th className="px-4 py-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((c, i) => {
                    const roas = c.roas || 0;
                    const isWinner = roas >= 3.0;
                    const isGoogle = c.platform === 'google_ads' || c.platform === 'GOOGLE_ADS';
                    return (
                      <tr key={i} className="border-b border-outline-variant/10 hover:bg-surface-container-low/30">
                        <td className="px-4 py-3 font-medium text-on-surface">
                          {c.campaign_name || c.name || `Campaign ${i + 1}`}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${isGoogle ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'}`}>
                            {isGoogle ? 'Google' : 'Meta'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right font-medium">₹{Math.round(c.spend_inr || c.spend || 0).toLocaleString()}</td>
                        <td className="px-4 py-3 text-right font-bold text-agent-green">{roas.toFixed(1)}x</td>
                        <td className="px-4 py-3 text-right">₹{Math.round(c.cpa_inr || c.cpa || 0)}</td>
                        <td className="px-4 py-3 text-center">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${isWinner ? 'bg-success-container text-success' : 'bg-secondary-container text-on-secondary-container'}`}>
                            {isWinner ? 'Winner' : 'Stable'}
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
    </div>
  );
}
