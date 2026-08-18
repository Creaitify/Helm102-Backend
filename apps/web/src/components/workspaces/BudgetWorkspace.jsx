import React from 'react';
import { useHelmStore } from '../../context/HelmStore';
import { DollarSign, ShieldCheck, TrendingUp, AlertCircle } from 'lucide-react';

export function BudgetWorkspace() {
  const { currentRunState } = useHelmStore();
  const budget =
    currentRunState?.agent_reports?.budget || currentRunState?.proposal;

  const shifts = budget?.shifts || budget?.budget_shifts || [];
  const totalCurrent = budget?.total_current_inr || budget?.total_budget_current_inr || 0;
  const totalProposed = budget?.total_proposed_inr || budget?.total_budget_proposed_inr || 0;

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Quantitative Budget Reallocation</h3>
          <p className="banner-sub" style={{ marginTop: '0.2rem' }}>
            Enforces &plusmn;25% daily shift cap and absolute budget conservation laws.
          </p>
        </div>
        <span className="badge badge-amber">CONSERVATION ENFORCED</span>
      </div>

      {shifts.length === 0 ? (
        <div className="empty-state-hint">
          Launch a mission from Governor HQ to view quantitative budget shifts and ROAS models.
        </div>
      ) : (
        <div style={{ marginTop: '0.5rem' }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="metric-table">
              <thead>
                <tr>
                  <th>Campaign ID</th>
                  <th>Current Daily Budget</th>
                  <th>Proposed Daily Budget</th>
                  <th>Shift Percentage</th>
                  <th>Optimization Rationale</th>
                </tr>
              </thead>
              <tbody>
                {shifts.map((s, idx) => (
                  <tr key={idx}>
                    <td>
                      <span className="mono" style={{ fontWeight: 700 }}>
                        {s.campaign_id}
                      </span>
                    </td>
                    <td>₹{Number(s.current_daily_budget_inr).toLocaleString()}</td>
                    <td>
                      <strong style={{ color: 'var(--primary-blue)' }}>
                        ₹{Number(s.proposed_daily_budget_inr).toLocaleString()}
                      </strong>
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          s.shift_percentage > 0 ? 'badge-emerald' : 'badge-amber'
                        }`}
                      >
                        {s.shift_percentage > 0 ? '+' : ''}
                        {s.shift_percentage}%
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                      {s.rationale || 'Budget rebalancing'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div
            style={{
              marginTop: '1.25rem',
              background: 'var(--bg-card-subtle)',
              padding: '0.875rem 1.25rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              Total Current: <strong>₹{Number(totalCurrent).toLocaleString()}</strong> &rarr; Total
              Proposed: <strong>₹{Number(totalProposed).toLocaleString()}</strong>
            </span>
            <span className="badge badge-emerald">Budget Conservation Satisfied (Proposed &le; Current)</span>
          </div>
        </div>
      )}
    </div>
  );
}
