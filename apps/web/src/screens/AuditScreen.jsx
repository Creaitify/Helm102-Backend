/**
 * Audit trail: every run, every hop, every envelope.
 *
 * This is the regulator-facing view — an append-only record of what each agent
 * received, what it decided, and why. Nothing here is summarized away.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { Chip, EmptyState, Icon, Spinner, relativeTime } from '../components/ui';
import { ContextBar } from '../components/Shell';

export function AuditScreen() {
  const [runs, setRuns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [trail, setTrail] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listRuns();
      setRuns([...list].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || ''))));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const open = async (runId) => {
    setSelected(runId);
    setTrail([]);
    try {
      setTrail(await api.runAudit(runId));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <ContextBar title="Audit Trail" subtitle="Append-only record of every run: each hop envelope, status, and rationale" />
      <div className="p-4 sm:p-7 max-w-[1100px]">

      {error && (
        <div className="rounded-xl border border-error/30 bg-error-container p-3 mb-4 text-body-sm text-on-error-container">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16 text-primary">
          <Spinner className="w-6 h-6" />
        </div>
      ) : runs.length === 0 ? (
        <EmptyState
          icon="gavel"
          title="No runs recorded yet"
          body="Run the pipeline to produce an auditable trail."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-5">
          <ul className="space-y-1.5 lg:max-h-[70vh] lg:overflow-y-auto lg:pr-1">
            {runs.map((run) => (
              <li key={run.run_id}>
                <button
                  onClick={() => open(run.run_id)}
                  className={`card w-full p-3 text-left transition-colors focus-ring ${
                    selected === run.run_id ? 'border-primary/50 bg-primary-fixed/30' : 'hover:border-primary/30'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-mono text-[11px] text-outline truncate">{run.run_id}</span>
                    <Chip label={run.status} />
                  </div>
                  <p className="text-body-sm text-on-surface line-clamp-2 leading-snug">
                    {run.objective || '—'}
                  </p>
                  <p className="rail-label mt-1">
                    hop {run.hop_index ?? 0} · {relativeTime(run.updated_at)}
                  </p>
                </button>
              </li>
            ))}
          </ul>

          <div>
            {!selected ? (
              <EmptyState
                icon="touch_app"
                title="Select a run"
                body="Pick a run on the left to inspect its envelope chain."
              />
            ) : trail.length === 0 ? (
              <div className="flex justify-center py-16 text-primary">
                <Spinner className="w-6 h-6" />
              </div>
            ) : (
              <ol className="space-y-3">
                {trail.map((envelope, index) => (
                  <Envelope key={index} envelope={envelope} />
                ))}
              </ol>
            )}
          </div>
        </div>
      )}
      </div>
    </>
  );
}

function Envelope({ envelope }) {
  const [open, setOpen] = useState(false);
  const payload = envelope.payload ?? envelope;
  const status = String(envelope.status || '').toLowerCase();

  return (
    <li className="card p-4">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className="w-7 h-7 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center font-mono text-[11px] font-bold shrink-0">
          {envelope.hop_index ?? '—'}
        </span>
        <span className="font-mono text-body-sm font-semibold text-on-surface">
          {envelope.source} → {envelope.target}
        </span>
        <Chip label={status} />
        <span className="rail-label ml-auto">{relativeTime(envelope.timestamp)}</span>
      </div>

      <p className="font-mono text-[11px] text-primary mb-1.5">{envelope.action}</p>
      <p className="text-body-sm text-on-surface-variant leading-relaxed">{envelope.rationale}</p>

      {envelope.error && (
        <p className="mt-2 text-body-sm text-error flex gap-1.5">
          <Icon name="error" size={16} fill className="shrink-0" />
          {envelope.error}
        </p>
      )}

      <button
        onClick={() => setOpen((value) => !value)}
        className="mt-3 flex items-center gap-1 rail-label hover:text-primary focus-ring rounded"
      >
        <Icon name={open ? 'expand_less' : 'expand_more'} size={16} />
        {open ? 'Hide payload' : 'Inspect payload'}
      </button>

      {open && (
        <pre className="mt-2 max-h-80 overflow-auto bg-surface-container-low rounded-lg p-3 text-[11px] font-mono text-on-surface-variant whitespace-pre-wrap break-words">
          {JSON.stringify(payload, null, 2)}
        </pre>
      )}
    </li>
  );
}
