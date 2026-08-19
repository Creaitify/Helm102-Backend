import React, { useState, useEffect } from 'react';
import { useHelmStore } from '../../context/HelmStore';

export function AuditPage() {
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
    <div className="max-w-4xl mx-auto w-full flex flex-col gap-6 py-4">
      <div className="border-b border-outline-variant/20 pb-4 flex items-center justify-between">
        <div>
          <h2 className="font-headline-xl text-xl font-bold text-on-surface">
            Immutable Envelope Audit Trail
          </h2>
          <p className="text-xs text-on-surface-variant mt-0.5">
            Append-only cryptographic record of all inter-agent handoff envelopes, checkpoints, and platform dispatches.
          </p>
        </div>
        <button
          onClick={fetchAudit}
          disabled={isLoading}
          className="text-xs font-label-mono text-primary bg-primary-fixed/30 hover:bg-primary-fixed/50 px-3 py-1.5 rounded-lg border border-primary/20 flex items-center gap-1.5 transition-colors"
        >
          <span className={`material-symbols-outlined text-[16px] ${isLoading ? 'animate-spin' : ''}`}>
            refresh
          </span>
          Refresh Log
        </button>
      </div>

      {trail.length === 0 ? (
        <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-8 text-center">
          <span className="material-symbols-outlined text-outline text-[36px] mb-2 block">
            receipt_long
          </span>
          <p className="text-sm font-bold text-on-surface mb-1">No Audit Envelopes Yet</p>
          <p className="text-xs text-outline">
            Launch a mission from the bottom bar or Landing page to record cryptographic handoff envelopes.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {trail.map((event, idx) => (
            <div
              key={idx}
              className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-4 shadow-sm"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="bg-primary/10 text-primary font-label-mono text-[10px] font-bold px-2 py-0.5 rounded">
                    H{event.hop_index}
                  </span>
                  <span className="font-bold text-xs text-on-surface">{event.action}</span>
                </div>
                <span className="text-[10px] font-label-mono text-outline">
                  {new Date(event.created_at).toLocaleTimeString()}
                </span>
              </div>

              <div className="flex items-center gap-2 text-xs font-label-mono text-outline mb-2">
                <span className="text-on-surface font-semibold">{event.source}</span>
                <span>&rarr;</span>
                <span className="text-primary font-semibold">{event.target}</span>
                <span
                  className={`ml-2 px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    event.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'
                  }`}
                >
                  {event.status.toUpperCase()}
                </span>
              </div>

              <p className="text-xs text-on-surface-variant mb-3">{event.rationale}</p>

              <pre className="bg-surface-container-low p-3 rounded-lg text-[11px] font-label-mono text-on-surface overflow-x-auto max-h-32">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
