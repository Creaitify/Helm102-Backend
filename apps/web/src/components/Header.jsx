import React from 'react';
import { useHelmStore } from '../context/HelmStore';
import { ShieldCheck, Cpu, Database, PlayCircle, Sparkles } from 'lucide-react';

export function Header() {
  const { health, switchModel } = useHelmStore();

  const handleModelChange = (e) => {
    const val = e.target.value;
    if (val === 'replay') {
      switchModel('replay', 'deterministic-replay-v1');
    } else if (val.startsWith('claude')) {
      switchModel('anthropic', val);
    } else {
      switchModel('gemini', val);
    }
  };

  const currentVal = health.gateway_mode === 'replay' ? 'replay' : (health.active_model || 'gemini-2.5-flash');

  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-badge">HELM 02</div>
        <div className="brand-title-group">
          <h1 className="brand-title">Governed Marketing Orchestration</h1>
          <p className="brand-subtitle">
            Governor Star-Relay &middot; Gemini Models &middot; Mureo Ad Connectors &middot; SEBI Gated
          </p>
        </div>
      </div>

      <div className="system-status-group">
        <div className="status-chip">
          <Database className="text-blue-600" style={{ width: 14, height: 14 }} />
          <span className="chip-label">DATA:</span>
          <span className="chip-value">{(health.data_source || 'SQLITE SYNTHETIC').toUpperCase()}</span>
        </div>

        <div className="status-chip" style={{ padding: '0.2rem 0.5rem' }}>
          <Cpu className="text-blue-600" style={{ width: 14, height: 14 }} />
          <span className="chip-label">MODEL:</span>
          <select
            value={currentVal}
            onChange={handleModelChange}
            style={{
              background: 'transparent',
              border: 'none',
              fontWeight: 700,
              fontSize: '0.75rem',
              color: 'var(--primary-blue)',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value="gemini-2.5-flash">GEMINI 2.5 FLASH</option>
            <option value="gemini-2.5-pro">GEMINI 2.5 PRO</option>
            <option value="gemini-2.0-flash">GEMINI 2.0 FLASH</option>
            <option value="claude-3-5-sonnet-20241022">CLAUDE 3.5 SONNET</option>
            <option value="replay">OFFLINE FAST / REPLAY</option>
          </select>
        </div>

        <div className="status-chip">
          <PlayCircle className="text-blue-600" style={{ width: 14, height: 14 }} />
          <span className="chip-label">DISPATCH:</span>
          <span className="chip-value">{health.dry_run ? 'DRY-RUN' : 'LIVE'}</span>
        </div>
      </div>
    </header>
  );
}

