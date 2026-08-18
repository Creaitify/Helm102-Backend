import React, { useState } from 'react';
import { useHelmStore } from '../../context/HelmStore';
import { ShieldCheck, AlertOctagon, CheckCircle2, Search } from 'lucide-react';

export function ComplianceWorkspace() {
  const { currentRunState } = useHelmStore();
  const [headline, setHeadline] = useState('Start Disciplined SIPs for Long-Term Growth');
  const [primaryText, setPrimaryText] = useState(
    'Mutual fund investments are subject to market risks, read all scheme related documents carefully.'
  );
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);

  const comp =
    currentRunState?.agent_reports?.compliance ||
    currentRunState?.proposal?.compliance_verdict;

  const handleScan = async () => {
    if (!headline.trim() && !primaryText.trim()) return;
    setIsScanning(true);
    try {
      const res = await fetch('/api/citations/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ headline, primary_text: primaryText }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setScanResult(data);
    } catch (err) {
      alert(`Compliance scan failed: ${err.message}`);
    } finally {
      setIsScanning(false);
    }
  };

  const isPass = comp ? (comp.status === 'pass' || comp.passed === true) : true;

  return (
    <div className="workspace-grid">
      {/* Left: Interactive Copy Scanner */}
      <div className="card">
        <div className="panel-header">
          <h3 className="panel-heading">Interactive SEBI Copy Tester</h3>
          <span className="badge badge-emerald">Deterministic Rule Gate</span>
        </div>
        <p className="panel-desc">
          Test any custom copy against SEBI Advertising Code and citation grounding rules.
        </p>

        <div className="form-group">
          <label className="form-label">Headline</label>
          <input
            type="text"
            className="form-input"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Primary Text</label>
          <textarea
            className="form-textarea"
            rows={4}
            value={primaryText}
            onChange={(e) => setPrimaryText(e.target.value)}
          />
        </div>

        <button
          type="button"
          disabled={isScanning}
          onClick={handleScan}
          className="btn btn-primary btn-sm"
          style={{ width: '100%' }}
        >
          <Search style={{ width: 14, height: 14 }} />
          {isScanning ? 'Scanning Rules...' : 'Scan Copy for SEBI Compliance'}
        </button>

        {scanResult && (
          <div
            style={{
              marginTop: '1.25rem',
              padding: '0.875rem',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: scanResult.status === 'pass' ? 'var(--accent-emerald-light)' : 'var(--accent-rose-light)',
              border: `1px solid ${scanResult.status === 'pass' ? '#a7f3d0' : '#fecaca'}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {scanResult.status === 'pass' ? (
                <CheckCircle2 style={{ width: 16, height: 16, color: 'var(--accent-emerald)' }} />
              ) : (
                <AlertOctagon style={{ width: 16, height: 16, color: 'var(--accent-rose)' }} />
              )}
              <span
                style={{
                  fontWeight: 700,
                  fontSize: '0.875rem',
                  color: scanResult.status === 'pass' ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                }}
              >
                {scanResult.status === 'pass' ? 'PASSED SEBI COMPLIANCE' : 'FLAGGED ISSUES'}
              </span>
            </div>
            <p style={{ fontSize: '0.75rem', marginTop: '0.3rem', color: 'var(--text-main)' }}>
              Grounding Score: <strong>{(scanResult.overall_score * 100).toFixed(0)}%</strong>
            </p>
          </div>
        )}
      </div>

      {/* Right: Mission Compliance Evaluation */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Orchestration SEBI Regulatory Verdict</h3>
          <span className={`badge ${isPass ? 'badge-emerald' : 'badge-rose'}`}>
            {isPass ? 'VERIFIED (PASS)' : 'FLAGGED (FAIL)'}
          </span>
        </div>

        {!comp ? (
          <div className="empty-state-hint">
            Launch a mission from Governor HQ to view statutory verification details.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.5rem' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: 'var(--bg-card-subtle)',
                padding: '0.875rem 1rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-color)',
              }}
            >
              <div>
                <span style={{ fontSize: '0.8125rem', fontWeight: 700 }}>Statutory Disclaimer:</span>
                <span
                  style={{ fontSize: '0.8125rem', marginLeft: '0.5rem', fontWeight: 700 }}
                  className={comp.has_mandatory_disclaimer ? 'text-green' : 'text-red'}
                >
                  {comp.has_mandatory_disclaimer ? 'Present & Verified ✓' : 'Missing ✗'}
                </span>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Rules Version: <strong>{comp.rules_version || 'SEBI_2026_AD_CODE'}</strong> · Loopbacks:{' '}
                <strong>{comp.loopback_count || 0}</strong>
              </div>
            </div>

            {comp.violations && comp.violations.length > 0 ? (
              <div>
                <h4 className="subheading" style={{ color: 'var(--accent-rose)' }}>
                  Flagged Compliance Violations
                </h4>
                {comp.violations.map((v, i) => (
                  <div
                    key={i}
                    style={{
                      background: 'var(--accent-rose-light)',
                      border: '1px solid #fecaca',
                      padding: '0.75rem',
                      borderRadius: 'var(--radius-sm)',
                      marginBottom: '0.5rem',
                    }}
                  >
                    <span className="badge badge-rose" style={{ fontSize: '0.7rem' }}>
                      PROHIBITED PHRASE
                    </span>
                    <p style={{ fontSize: '0.8125rem', marginTop: '0.3rem' }}>
                      {typeof v === 'string' ? v : JSON.stringify(v)}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div
                style={{
                  background: 'var(--accent-emerald-light)',
                  border: '1px solid #a7f3d0',
                  padding: '1.25rem',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div style={{ fontWeight: 700, color: 'var(--accent-emerald)', fontSize: '0.9375rem' }}>
                  ✓ Full Statutory Compliance Verified
                </div>
                <p style={{ fontSize: '0.8125rem', marginTop: '0.25rem', color: 'var(--text-main)' }}>
                  Copy audited against SEBI regulations. Guaranteed return assertions prohibited; mandatory risk
                  disclaimers verified.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
