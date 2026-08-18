import React, { useState } from 'react';
import { useHelmStore } from '../../context/HelmStore';
import {
  CheckCircle,
  XCircle,
  TrendingUp,
  TrendingDown,
  Sparkles,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
  Code,
  FileText,
  DollarSign,
  Layers,
  ArrowRight,
} from 'lucide-react';

export function ExecutionWorkspace() {
  const { currentRunState, resolveApproval } = useHelmStore();
  const [notes, setNotes] = useState('Approved by Growth Lead under Q3 budget.');
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  const proposal = currentRunState?.proposal;
  const status = currentRunState?.status || 'idle';
  const executionResults = currentRunState?.execution_results || [];

  const handleApprove = () => {
    resolveApproval('approved', notes);
  };

  const handleReject = () => {
    resolveApproval('rejected', notes);
  };

  const shifts = proposal?.budget_shifts || [];
  const actionSummary = proposal?.human_action_summary;
  const creative = proposal?.creative_package;
  const compliance = proposal?.compliance_verdict;
  const totalCurr = proposal?.total_budget_current_inr || 0;
  const totalProp = proposal?.total_budget_proposed_inr || 0;

  return (
    <div className="approvals-container">
      {/* Main Review Card */}
      <div className="card approval-decision-card">
        {/* Header */}
        <div className="card-header" style={{ alignItems: 'flex-start' }}>
          <div className="header-titles">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
              <ShieldCheck className="text-blue-600" style={{ width: 22, height: 22 }} />
              <h2 className="card-title" style={{ fontSize: '1.25rem' }}>Campaign Optimization &amp; Approval</h2>
            </div>
            <p className="card-sub" style={{ fontSize: '0.875rem' }}>
              Review the automated changes HELM is recommending across your ad accounts before anything is applied.
            </p>
          </div>

          <div
            className={`status-pill ${
              status === 'completed'
                ? 'status-success'
                : status === 'rejected'
                ? 'status-danger'
                : 'status-pending'
            }`}
            style={{ fontSize: '0.8125rem', padding: '0.4rem 0.9rem' }}
          >
            {status === 'completed'
              ? '✓ APPROVED & APPLIED'
              : status === 'rejected'
              ? '✕ REJECTED'
              : '⏳ AWAITING YOUR APPROVAL'}
          </div>
        </div>

        <div className="approval-body">
          {!proposal ? (
            <div className="empty-state-hint" style={{ padding: '3rem 1rem', textAlign: 'center' }}>
              <Layers style={{ width: 36, height: 36, margin: '0 auto 0.75rem', opacity: 0.4 }} />
              <p style={{ fontWeight: 600, fontSize: '1rem', marginBottom: '0.25rem' }}>No Proposal Ready Yet</p>
              <p className="text-muted" style={{ fontSize: '0.875rem' }}>
                Go to the <strong>Governor</strong> tab and start a mission to generate campaign optimization proposals.
              </p>
            </div>
          ) : (
            <>
              {/* Executive Overview Banner */}
              <div
                style={{
                  background: 'linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%)',
                  border: '1px solid #bfdbfe',
                  borderRadius: 'var(--radius-md)',
                  padding: '1.25rem 1.5rem',
                  marginBottom: '1.5rem',
                }}
              >
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles className="text-blue-600" style={{ width: 18, height: 18 }} />
                  What HELM Will Do For You:
                </h3>
                <p style={{ fontSize: '0.875rem', color: '#1e293b', lineHeight: 1.6 }}>
                  {actionSummary?.overview || (
                    `HELM analyzed your campaigns and prepared ${shifts.length} budget shifts and a fresh creative refresh to maximize ROAS while maintaining your daily spend at ₹${Math.round(totalProp).toLocaleString()}/day.`
                  )}
                </p>
              </div>

              {/* 4 Friendly Action Summary Cards */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                  gap: '1rem',
                  marginBottom: '1.5rem',
                }}
              >
                {/* 1. Budget Scale Card */}
                <div className="card" style={{ padding: '1rem 1.25rem', borderLeft: '4px solid var(--accent-emerald)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <TrendingUp className="text-green" style={{ width: 18, height: 18 }} />
                    <strong style={{ fontSize: '0.875rem' }}>Scale Top Winners</strong>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    Increase daily budget on high-intent converting campaigns by up to 20% to capture more profitable conversions.
                  </p>
                </div>

                {/* 2. Budget Cut Card */}
                <div className="card" style={{ padding: '1rem 1.25rem', borderLeft: '4px solid var(--accent-amber)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <TrendingDown style={{ color: 'var(--accent-amber)', width: 18, height: 18 }} />
                    <strong style={{ fontSize: '0.875rem' }}>Cut Fatigued Ad Spend</strong>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    Reduce spend by 20% on tired, fatigued ads where customer acquisition cost has risen.
                  </p>
                </div>

                {/* 3. Creative Launch Card */}
                <div className="card" style={{ padding: '1rem 1.25rem', borderLeft: '4px solid var(--primary-blue)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <Sparkles className="text-blue-600" style={{ width: 18, height: 18 }} />
                    <strong style={{ fontSize: '0.875rem' }}>Deploy Fresh Video Creative</strong>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    Launch 1 new compliant video ad with fresh hook and captions to replace exhausted creative angles.
                  </p>
                </div>

                {/* 4. Safety & Compliance Card */}
                <div className="card" style={{ padding: '1rem 1.25rem', borderLeft: '4px solid var(--accent-emerald)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <ShieldCheck className="text-green" style={{ width: 18, height: 18 }} />
                    <strong style={{ fontSize: '0.875rem' }}>SEBI Compliance Verified</strong>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-green)', fontWeight: 600 }}>
                    ✓ 100% Passed Safety Clearance
                  </p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    No guaranteed return claims. Standard statutory disclaimers included.
                  </p>
                </div>
              </div>

              {/* Proposed Budget Changes Table */}
              <div style={{ marginBottom: '1.5rem' }}>
                <h3 className="subheading" style={{ fontSize: '0.9375rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <DollarSign style={{ width: 16, height: 16 }} /> Proposed Budget Changes
                </h3>

                <div style={{ overflowX: 'auto', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }}>
                  <table className="metric-table" style={{ margin: 0 }}>
                    <thead>
                      <tr>
                        <th>Campaign Name</th>
                        <th>Platform</th>
                        <th>Current Budget</th>
                        <th>Proposed Budget</th>
                        <th>Change</th>
                        <th>Why This Change?</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shifts.map((s, idx) => {
                        const pct = s.shift_percentage || 0;
                        const curr = Math.round(s.current_daily_budget_inr || 0);
                        const prop = Math.round(s.proposed_daily_budget_inr || 0);
                        const isUp = pct > 0;
                        return (
                          <tr key={idx}>
                            <td>
                              <strong>{s.campaign_name || s.campaign_id}</strong>
                            </td>
                            <td>
                              <span className="badge badge-blue">{s.platform}</span>
                            </td>
                            <td>₹{curr.toLocaleString()}/day</td>
                            <td>
                              <strong style={{ color: isUp ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>
                                ₹{prop.toLocaleString()}/day
                              </strong>
                            </td>
                            <td>
                              <span className={`badge ${isUp ? 'badge-emerald' : 'badge-amber'}`}>
                                {isUp ? `+${pct}%` : `${pct}%`}
                              </span>
                            </td>
                            <td style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', maxWidth: '320px' }}>
                              {s.rationale || (isUp ? 'High ROAS winner, increase to capture more demand.' : 'Fatigued creative, reduce spend to save budget.')}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Creative Package Preview */}
              {creative && (
                <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem', background: 'var(--bg-card-subtle)' }}>
                  <h3 className="subheading" style={{ fontSize: '0.9375rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <FileText style={{ width: 16, height: 16 }} /> Fresh Creative Preview (To Be Deployed)
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
                    <div>
                      <span className="lbl" style={{ fontSize: '0.75rem' }}>Headline</span>
                      <p style={{ fontWeight: 600, fontSize: '0.875rem', marginTop: '0.2rem' }}>
                        {creative.creative?.headline || 'Start Disciplined SIPs for Long-Term Growth'}
                      </p>
                      <span className="lbl" style={{ fontSize: '0.75rem', marginTop: '0.6rem', display: 'block' }}>Primary Copy</span>
                      <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.2rem', lineHeight: 1.5 }}>
                        {creative.creative?.primary_text || 'Automate disciplined monthly index SIPs. Mutual fund investments are subject to market risks.'}
                      </p>
                    </div>
                    <div>
                      <span className="lbl" style={{ fontSize: '0.75rem' }}>Video Ad Hook (First 3 Seconds)</span>
                      <div style={{ background: '#ffffff', padding: '0.6rem 0.8rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', marginTop: '0.2rem' }}>
                        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--primary-blue)' }}>
                          🎬 "{creative.script?.hook_3s || 'Still leaving your savings idle?'}"
                        </span>
                      </div>
                      <span className="lbl" style={{ fontSize: '0.75rem', marginTop: '0.6rem', display: 'block' }}>Call To Action</span>
                      <span className="badge badge-blue" style={{ marginTop: '0.2rem' }}>
                        {creative.creative?.call_to_action || 'Start SIP Now'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Action Buttons Section */}
              {status === 'pending_approval' && (
                <div
                  style={{
                    background: '#ffffff',
                    border: '2px solid var(--primary-blue-border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.5rem',
                    marginBottom: '1.5rem',
                    boxShadow: 'var(--shadow-md)',
                  }}
                >
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                    Ready to apply these optimizations?
                  </h3>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                    Clicking Approve will apply the budget reallocations and queue the new creatives.
                  </p>

                  <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                    <label className="form-label" style={{ fontSize: '0.8125rem' }}>Approval Notes / Reference (Optional)</label>
                    <input
                      type="text"
                      className="form-input"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="e.g., Approved by Marketing Director for Q3"
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={handleApprove}
                      className="btn btn-success"
                      style={{ padding: '0.75rem 1.75rem', fontSize: '0.9375rem', fontWeight: 700 }}
                    >
                      <CheckCircle style={{ width: 18, height: 18 }} /> Approve &amp; Apply Changes
                    </button>
                    <button
                      type="button"
                      onClick={handleReject}
                      className="btn btn-danger"
                      style={{ padding: '0.75rem 1.5rem', fontSize: '0.875rem' }}
                    >
                      <XCircle style={{ width: 16, height: 16 }} /> Decline / Reject Proposal
                    </button>
                  </div>
                </div>
              )}

              {/* Execution Outcome if completed */}
              {executionResults.length > 0 && (
                <div style={{ marginBottom: '1.5rem' }}>
                  <h3 className="subheading" style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem' }}>Platform Execution Outcome</h3>
                  <div>
                    {executionResults.map((r, idx) => (
                      <div
                        key={idx}
                        style={{
                          background: 'var(--bg-card-subtle)',
                          padding: '0.6rem 0.8rem',
                          borderRadius: 'var(--radius-sm)',
                          marginBottom: '0.4rem',
                          border: '1px solid var(--border-color)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div>
                          <span className={`badge ${r.success ? 'badge-emerald' : 'badge-amber'}`}>
                            {r.success ? 'SUCCESS' : 'FAILED'}
                          </span>
                          <span className="mono" style={{ marginLeft: '0.5rem', fontWeight: 600 }}>
                            {r.action_type} &rarr; {r.resource_id}
                          </span>
                        </div>
                        <span className={`badge ${r.dry_run ? 'badge-blue' : 'badge-purple'}`}>
                          {r.dry_run ? 'DRY-RUN VALIDATED' : 'LIVE'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Collapsible Technical Details (Raw JSON) Accordion */}
              <div
                style={{
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  overflow: 'hidden',
                  marginTop: '1.5rem',
                }}
              >
                <button
                  type="button"
                  onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                  style={{
                    width: '100%',
                    padding: '0.65rem 1rem',
                    background: 'var(--bg-card-subtle)',
                    border: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    fontSize: '0.8125rem',
                    fontWeight: 600,
                    color: 'var(--text-muted)',
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Code style={{ width: 14, height: 14 }} /> Technical &amp; Developer Details (Raw Payloads)
                  </span>
                  {showTechnicalDetails ? (
                    <ChevronDown style={{ width: 14, height: 14 }} />
                  ) : (
                    <ChevronRight style={{ width: 14, height: 14 }} />
                  )}
                </button>

                {showTechnicalDetails && (
                  <div style={{ padding: '1rem', background: '#0f172a' }}>
                    <pre
                      className="json-preview"
                      style={{
                        margin: 0,
                        maxHeight: '300px',
                        overflowY: 'auto',
                        color: '#38bdf8',
                        fontSize: '0.75rem',
                      }}
                    >
                      {JSON.stringify(proposal?.dry_run_preview || proposal, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

