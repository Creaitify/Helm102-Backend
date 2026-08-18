import React, { useState } from 'react';
import { useHelmStore } from '../../context/HelmStore';
import { CheckCircle, XCircle, Code, ShieldCheck, PlayCircle } from 'lucide-react';

export function ExecutionWorkspace() {
  const { currentRunState, resolveApproval } = useHelmStore();
  const [notes, setNotes] = useState('Approved by Growth Lead under Q3 budget.');

  const proposal = currentRunState?.proposal;
  const status = currentRunState?.status || 'idle';
  const executionResults = currentRunState?.execution_results || [];

  const handleApprove = () => {
    resolveApproval('approved', notes);
  };

  const handleReject = () => {
    resolveApproval('rejected', notes);
  };

  return (
    <div className="approvals-container">
      <div className="card approval-decision-card">
        <div className="card-header">
          <div className="header-titles">
            <h2 className="card-title">Human-in-the-Loop Execution Signoff</h2>
            <p className="card-sub">
              State checkpointer is locked. Platform writes dispatch strictly upon explicit operator approval.
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
          >
            {status === 'completed'
              ? 'APPROVED & EXECUTED'
              : status === 'rejected'
              ? 'REJECTED BY OPERATOR'
              : 'AWAITING HUMAN DECISION'}
          </div>
        </div>

        <div className="approval-body">
          <div className="approval-summary-panel">
            <div className="summary-metric">
              <span className="lbl">Active Run ID</span>
              <span className="val mono text-blue">{currentRunState?.run_id || '—'}</span>
            </div>
            <div className="summary-metric">
              <span className="lbl">Compliance Status</span>
              <span className="val text-green">
                {(proposal?.compliance_verdict?.status || 'PASS').toUpperCase()}
              </span>
            </div>
            <div className="summary-metric">
              <span className="lbl">Proposed Budget/Day</span>
              <span className="val text-blue">
                ₹{proposal?.total_budget_proposed_inr || 0}/day
              </span>
            </div>
            <div className="summary-metric">
              <span className="lbl">Dispatch Mode</span>
              <span className="val mono">DRY-RUN PREVIEW</span>
            </div>
          </div>

          <div className="payload-preview-section">
            <h3 className="subheading" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Code style={{ width: 14, height: 14 }} /> Platform Execution Payload Preview
            </h3>
            <pre className="json-preview">
              {JSON.stringify(proposal?.dry_run_preview || { status: 'No active proposal loaded' }, null, 2)}
            </pre>
          </div>

          {status === 'pending_approval' && (
            <div className="decision-form-block">
              <div className="form-group">
                <label className="form-label">Operator Rationale &amp; Audit Notes</label>
                <input
                  type="text"
                  className="form-input"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. Approved under Q3 Growth Marketing budget."
                />
              </div>

              <div className="decision-button-row">
                <button type="button" onClick={handleApprove} className="btn btn-success">
                  <CheckCircle style={{ width: 16, height: 16 }} /> Approve &amp; Execute Platform Changes
                </button>
                <button type="button" onClick={handleReject} className="btn btn-danger">
                  <XCircle style={{ width: 16, height: 16 }} /> Reject Proposal
                </button>
              </div>
            </div>
          )}

          {executionResults.length > 0 && (
            <div style={{ marginTop: '1.5rem' }}>
              <h3 className="subheading">Platform Execution Outcome</h3>
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
                      {r.dry_run ? 'DRY-RUN' : 'LIVE'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
