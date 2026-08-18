import React from 'react';
import { useHelmStore } from '../context/HelmStore';
import { ShieldCheck, Cpu, Database, PlayCircle } from 'lucide-react';

export function Header() {
  const { health } = useHelmStore();

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
          <Database className="w-3.5 h-3.5 text-blue-600" style={{ width: 14, height: 14 }} />
          <span className="chip-label">DATA:</span>
          <span className="chip-value">{(health.data_source || 'SQLITE SYNTHETIC').toUpperCase()}</span>
        </div>

        <div className="status-chip">
          <Cpu className="w-3.5 h-3.5 text-blue-600" style={{ width: 14, height: 14 }} />
          <span className="chip-label">MODEL:</span>
          <span className="chip-value">{(health.active_model || 'GEMINI 2.5').toUpperCase()}</span>
        </div>

        <div className="status-chip">
          <PlayCircle className="w-3.5 h-3.5 text-blue-600" style={{ width: 14, height: 14 }} />
          <span className="chip-label">DISPATCH:</span>
          <span className="chip-value">{health.dry_run ? 'DRY-RUN' : 'LIVE'}</span>
        </div>
      </div>
    </header>
  );
}
