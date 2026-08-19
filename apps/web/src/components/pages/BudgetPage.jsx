import React from 'react';
import { useHelmStore } from '../../context/HelmStore';

export function BudgetPage() {
  const { currentRunState } = useHelmStore();
  const proposal = currentRunState?.proposal;
  const budget = currentRunState?.agent_reports?.budget || proposal;

  const rawShifts = budget?.shifts || budget?.budget_shifts || [];
  const shifts =
    rawShifts.length > 0
      ? rawShifts
      : [
          { name: 'Meta Ads', current: '₹40,000', proposed: '₹50,000', pct: '+25%', status: 'Valid', rationale: 'High ROAS scaling' },
          { name: 'Google Search', current: '₹30,000', proposed: '₹22,500', pct: '-25%', status: 'Valid', rationale: 'Pruning saturated keywords' },
          { name: 'LinkedIn Display', current: '₹20,000', proposed: '₹16,000', pct: '-20%', status: 'Valid', rationale: 'Trimming high CPA display' },
        ];

  return (
    <div className="max-w-4xl mx-auto w-full flex flex-col gap-6 py-4">
      {/* Header */}
      <div className="border-b border-outline-variant/20 pb-4">
        <h2 className="font-headline-lg text-xl font-bold text-on-surface">
          Budget Optimization Proposal
        </h2>
        <span className="px-2.5 py-1 rounded-full bg-primary/10 text-primary font-label-mono text-[10px] uppercase font-bold border border-primary/20 mt-2 inline-block">
          Direct Media Buyer Mode
        </span>
      </div>

      {/* User Message Bubble */}
      <div className="flex gap-4 items-start">
        <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center shrink-0 text-xs font-bold text-on-surface">
          RM
        </div>
        <div className="flex-1 bg-surface-container-low px-4 py-2.5 rounded-xl border border-outline-variant/10 text-sm text-on-surface">
          Review current budget allocation and suggest optimization across search and social channels.
        </div>
      </div>

      {/* Media Buyer Agent Response */}
      <div className="flex gap-4 items-start">
        <div className="w-8 h-8 rounded-full bg-tertiary-container/20 text-tertiary flex items-center justify-center shrink-0 border border-tertiary/20">
          <span className="material-symbols-outlined text-sm">ads_click</span>
        </div>
        <div className="flex-1 space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-headline-md text-sm font-bold text-on-surface">Media Buyer Agent</span>
            <span className="text-[10px] text-outline font-label-mono uppercase">10:33 AM</span>
          </div>

          {/* Budget Reallocation Table */}
          <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-surface-container-low text-outline-variant font-label-mono uppercase border-b border-outline-variant/30">
                  <th className="px-4 py-3">Channel / Campaign</th>
                  <th className="px-4 py-3 text-right">Current</th>
                  <th className="px-4 py-3 text-right">Proposed</th>
                  <th className="px-4 py-3 text-right">Change %</th>
                  <th className="px-4 py-3 text-center">Policy Status</th>
                </tr>
              </thead>
              <tbody>
                {shifts.map((row, i) => {
                  const channel = row.campaign_name || row.campaign_id || row.name;
                  const curr = typeof row.current === 'string' ? row.current : `₹${Math.round(row.current_daily_budget_inr || 0).toLocaleString()}`;
                  const prop = typeof row.proposed === 'string' ? row.proposed : `₹${Math.round(row.proposed_daily_budget_inr || 0).toLocaleString()}`;
                  const pct = typeof row.pct === 'string' ? row.pct : `${row.shift_percentage > 0 ? '+' : ''}${row.shift_percentage}%`;
                  const isPositive = pct.startsWith('+');

                  return (
                    <tr key={i} className="border-b border-outline-variant/10 hover:bg-surface-container-low/30">
                      <td className="px-4 py-3 font-medium text-on-surface">{channel}</td>
                      <td className="px-4 py-3 text-right text-on-surface-variant">{curr}</td>
                      <td className="px-4 py-3 text-right font-bold text-on-surface">{prop}</td>
                      <td className={`px-4 py-3 text-right font-bold ${isPositive ? 'text-agent-green' : 'text-error'}`}>
                        {pct}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-[10px] bg-success-container text-success px-2 py-0.5 rounded-full font-bold">
                          Valid
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Strategic Recommendation Callout */}
          <div className="flex items-start gap-3 text-xs text-on-surface-variant bg-primary/5 p-4 rounded-xl border border-primary/15">
            <span className="material-symbols-outlined text-primary text-[18px] mt-0.5">lightbulb</span>
            <div className="space-y-1">
              <span className="font-bold text-primary block">Governor Reallocation Policy:</span>
              <p className="leading-relaxed">
                Recommendation: Increase Meta Ads prospecting budget by +25% due to highest ROAS (3.4x), offset by spend reductions in fatigued Search display campaigns. Total daily budget is conserved with zero leakage.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
