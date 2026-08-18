import React, { useState, useEffect } from 'react';
import { useHelmStore } from '../../context/HelmStore';
import { RefreshCw, Clock, ArrowRight } from 'lucide-react';

export function AuditWorkspace() {
  const { currentRunId } = useHelmStore();
  const [trail, setTrail] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchAudit = async () => {
    if (!currentRunId) return;
    setIsLoading(true);
    try {
      const res = await fetch(`/api/runs/${currentRunId}/audit`);
      if (res.ok) {
        const data = await res.json();
        setTrail(data);
      }
    } catch (err) {
      console.warn('Could not fetch audit trail', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAudit();
  }, [currentRunId]);

  return (
    <div className="audit-container">
      <div className="card audit-card">
        <div className="card-header">
          <div className="header-titles">
            <h2 className="card-title">Immutable Envelope Audit Trail</h2>
            <p className="card-sub">
              Append-only cryptographic record of all inter-agent envelopes, state checkpoints, and platform dispatches.
            </p>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={fetchAudit}
            disabled={isLoading}
          >
            <RefreshCw
              style={{ width: 14, height: 14 }}
              className={isLoading ? 'animate-spin' : ''}
            />{' '}
            Refresh Log
          </button>
        </div>

        <div className="audit-body">
          {trail.length === 0 ? (
            <div className="empty-state-hint">
              {currentRunId
                ? 'No audit events recorded for this run.'
                : 'Select or launch a mission to view its immutable audit envelopes.'}
            </div>
          ) : (
            <div className="audit-timeline">
              {trail.map((event, idx) => (
                <div key={idx} className="audit-entry">
                  <div className="audit-hop-badge">H{event.hop_index}</div>
                  <div className="audit-details">
                    <div className="audit-meta-row">
                      <span className="audit-action">{event.action}</span>
                      <span className="audit-time">
                        <Clock style={{ width: 12, height: 12, display: 'inline', marginRight: 4 }} />
                        {new Date(event.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="audit-route">
                      <span className="mono">{event.source}</span> &rarr;{' '}
                      <span className="mono">{event.target}</span>
                      <span
                        className={`badge ${
                          event.status === 'success' ? 'badge-emerald' : 'badge-amber'
                        }`}
                        style={{ marginLeft: '0.5rem' }}
                      >
                        {event.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="audit-rationale">{event.rationale}</div>
                    <pre
                      className="json-preview"
                      style={{ maxHeight: '120px', fontSize: '0.75rem', marginBottom: 0 }}
                    >
                      {JSON.stringify(event.payload, null, 2)}
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
