/**
 * Pipeline — run the full governed relay and approve what it proposes.
 *
 * The six hops are shown as a vertical track that fills as the run advances,
 * so it is always obvious which specialist is working and what it concluded.
 * The run stops at the approval gate; nothing dispatches without a decision.
 */

import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { useHelm } from '../store';
import { ContextBar } from '../components/Shell';
import { Button, Chip, Icon, Spinner, formatINR } from '../components/ui';


const HOPS = [
  { action: 'INGEST_OBJECTIVE', label: 'Objective', agent: 'Governor', icon: 'flag' },
  { action: 'FETCH_AND_ANALYZE_CAMPAIGNS', label: 'Performance analysis', agent: 'Analyst', icon: 'query_stats' },
  { action: 'GENERATE_CREATIVE_PACKAGE', label: 'Creative generation', agent: 'Creative', icon: 'palette' },
  { action: 'VERIFY_SEBI_REGULATORY', label: 'Compliance check', agent: 'Compliance', icon: 'verified_user' },
  { action: 'PROPOSE_BUDGET_REALLOCATION', label: 'Budget optimization', agent: 'Media Buyer', icon: 'ads_click' },
  { action: 'SUBMIT_PROPOSAL_FOR_APPROVAL', label: 'Approval gate', agent: 'You', icon: 'how_to_reg' },
];

const PRESETS = [
  'Reduce CPA and scale winning campaigns while staying compliant',
  'Refresh fatigued creative and rebalance budget toward what converts',
  'Prepare a quarterly optimization plan I can approve today',
];

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function PipelineScreen() {
  const { run, runBusy, startRun, decideRun, set } = useHelm();
  const [objective, setObjective] = useState(PRESETS[0]);
  const [notes, setNotes] = useState('');
  const [pending, setPending] = useState([]);
  const [attachment, setAttachment] = useState(null);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    api
      .listRuns()
      .then((runs) => setPending(runs.filter((r) => r.status === 'pending_approval')))
      .catch(() => {});
  }, [run?.status]);

  const handleFile = (file) => {
    if (!file) return;
    const name = file.name.toLowerCase();
    const valid =
      name.endsWith('.csv') ||
      name.endsWith('.xlsx') ||
      name.endsWith('.xls') ||
      name.endsWith('.json') ||
      name.endsWith('.pdf');
    if (!valid) {
      alert('Please upload a .csv, .xlsx, .xls, .json, or .pdf dataset.');
      return;
    }
    if (file.size === 0) {
      alert('The selected file is empty. Please upload a dataset or document with content.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      setAttachment({
        file,
        filename: file.name,
        file_content: e.target.result,
        size: file.size,
      });
    };
    reader.readAsDataURL(file);
  };

  const handleFileSelect = (event) => {
    const file = event.target.files?.[0];
    if (file) handleFile(file);
    event.target.value = '';
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const removeAttachment = () => {
    setAttachment(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleStart = () => {
    const obj =
      objective.trim() ||
      (attachment ? `Analyze and optimize ${attachment.filename || 'attached dataset'}` : '');
    if (!obj || runBusy) return;
    startRun(obj, attachment);
    setAttachment(null);
  };

  const resume = async (runId) => {
    try {
      set({ run: await api.getRun(runId) });
    } catch (err) {
      set({ error: err.message });
    }
  };

  return (
    <>
      <ContextBar
        title="Pipeline"
        subtitle="Six governed hops, ending at your approval — nothing dispatches on its own"
      />

      <div className="p-4 sm:p-7 max-w-[1200px] space-y-6">
        {/* Launcher */}
        <section
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            if (!e.currentTarget.contains(e.relatedTarget)) {
              setDragging(false);
            }
          }}
          onDrop={handleDrop}
          className={`card p-5 transition-colors ${
            dragging ? 'border-primary bg-primary/5 ring-2 ring-primary/20' : ''
          }`}
        >
          <h2 className="font-headline text-headline-md text-on-surface mb-1">Run the pipeline</h2>
          <p className="text-body-sm text-on-surface-variant mb-4">
            State a business objective or attach a dataset (.csv, .xlsx, .xls, .json, .pdf). The Governor routes it through every specialist and
            assembles one proposal for you to approve.
          </p>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".csv,.xlsx,.xls,.json,.pdf,text/csv,application/json,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
            className="hidden"
            aria-label="Upload dataset for pipeline"
          />

          <textarea
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
            rows={2}
            aria-label="Objective"
            className="w-full resize-none rounded-lg border border-outline-variant/50 bg-surface-container-lowest px-3.5 py-2.5 text-body-md text-on-surface placeholder:text-outline focus-ring focus:border-primary/50"
            placeholder={
              attachment
                ? `Run pipeline on ${attachment.filename}…`
                : 'e.g. Reduce CPA and scale winning campaigns'
            }
          />

          {/* Attachment chip */}
          {attachment && (
            <div className="flex items-center gap-2 mt-3 px-3 py-1.5 rounded-lg bg-surface-container-highest border border-outline-variant/60 w-fit max-w-full shadow-sm">
              <Icon name="attach_file" size={16} className="text-primary shrink-0" />
              <span className="font-mono text-body-sm text-on-surface truncate">
                {attachment.filename}
              </span>
              <span className="rail-label text-[11px] text-on-surface-variant">
                ({formatBytes(attachment.size)})
              </span>
              <button
                type="button"
                onClick={removeAttachment}
                className="p-1 rounded-md text-outline hover:text-error hover:bg-surface-container transition-colors ml-1 focus-ring"
                title="Remove attachment"
                aria-label="Remove attachment"
              >
                <Icon name="close" size={14} />
              </button>
            </div>
          )}

          <div className="flex flex-wrap gap-2 mt-3">
            {PRESETS.map((preset) => (
              <button
                key={preset}
                onClick={() => setObjective(preset)}
                className="px-3 py-1.5 rounded-lg border border-outline-variant/50 text-body-sm text-on-surface-variant hover:border-primary/50 hover:text-primary transition-colors focus-ring"
              >
                {preset.slice(0, 46)}…
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 mt-4">
            <Button
              icon="rocket_launch"
              disabled={(!objective.trim() && !attachment) || runBusy}
              onClick={handleStart}
            >
              {runBusy ? 'Running…' : 'Start pipeline'}
            </Button>
            <Button
              variant="outline"
              icon="attach_file"
              disabled={runBusy}
              onClick={() => fileInputRef.current?.click()}
              title="Attach dataset (.csv, .xlsx, .xls, .json)"
            >
              {attachment ? 'Change dataset' : 'Attach dataset'}
            </Button>
          </div>
        </section>


        {/* Other runs waiting on a decision */}
        {pending.length > 0 && !run && (
          <section className="card p-5">
            <h2 className="font-headline text-headline-md text-on-surface mb-3">
              Awaiting your approval
            </h2>
            <ul className="space-y-2">
              {pending.map((p) => (
                <li key={p.run_id}>
                  <button
                    onClick={() => resume(p.run_id)}
                    className="w-full flex items-center gap-3 p-3 rounded-lg border border-amber-200 bg-amber-50 hover:bg-amber-100 transition-colors text-left focus-ring"
                  >
                    <Icon name="pending_actions" size={18} className="text-amber-700 shrink-0" fill />
                    <span className="flex-1 min-w-0">
                      <span className="block text-body-sm font-medium text-amber-900 truncate">
                        {p.objective}
                      </span>
                      <span className="block font-mono text-[11px] text-amber-800/80">{p.run_id}</span>
                    </span>
                    <Icon name="arrow_forward" size={16} className="text-amber-700 shrink-0" />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {run && (
          <>
            <RunTrack run={run} />
            {run.status === 'pending_approval' && (
              <ApprovalGate run={run} notes={notes} setNotes={setNotes} onDecide={decideRun} busy={runBusy} />
            )}
            {run.status === 'failed' && (
              <div className="card p-5 border-error/30 bg-error-container">
                <p className="font-headline text-headline-md text-on-error-container mb-1">
                  Run failed
                </p>
                <p className="text-body-sm text-on-error-container/90">{run.error}</p>
              </div>
            )}
            {['completed', 'rejected'].includes(run.status) && <Outcome run={run} />}
          </>
        )}
      </div>
    </>
  );
}

function RunTrack({ run }) {
  const byAction = Object.fromEntries((run.hops || []).map((h) => [h.action, h]));
  const doneCount = (run.hops || []).length;

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h2 className="font-headline text-headline-md text-on-surface">Run progress</h2>
          <p className="font-mono text-[11px] text-outline mt-0.5">{run.run_id}</p>
        </div>
        <Chip label={run.status} />
      </div>

      <ol className="relative">
        {HOPS.map((hop, index) => {
          const envelope = byAction[hop.action];
          const done = Boolean(envelope);
          const active = !done && index === doneCount && run.status === 'running';
          const degraded = envelope?.status === 'degraded';

          return (
            <li key={hop.action} className="flex gap-4 pb-5 last:pb-0 relative">
              {index < HOPS.length - 1 && (
                <span
                  className={`absolute left-[15px] top-9 bottom-0 w-0.5 ${
                    done ? 'bg-primary' : 'bg-outline-variant/50'
                  }`}
                  aria-hidden="true"
                />
              )}

              <span
                className={`relative z-10 w-8 h-8 rounded-full grid place-items-center shrink-0 border-2 ${
                  done
                    ? degraded
                      ? 'bg-amber-500 border-amber-500 text-white'
                      : 'bg-primary border-primary text-on-primary'
                    : active
                      ? 'bg-surface-container-lowest border-primary text-primary'
                      : 'bg-surface-container border-outline-variant/50 text-outline'
                }`}
              >
                {active ? (
                  <Spinner className="w-3.5 h-3.5" />
                ) : (
                  <Icon name={done ? (degraded ? 'warning' : 'check') : hop.icon} size={16} fill={done} />
                )}
              </span>

              <div className="min-w-0 flex-1 pt-0.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`font-headline text-body-md font-semibold ${
                      done || active ? 'text-on-surface' : 'text-outline'
                    }`}
                  >
                    {hop.label}
                  </span>
                  <span className="rail-label">{hop.agent}</span>
                  {degraded && <Chip label="degraded" />}
                </div>
                {envelope?.rationale && (
                  <p className="text-body-sm text-on-surface-variant mt-1 leading-relaxed">
                    {envelope.rationale}
                  </p>
                )}
                {active && (
                  <p className="text-body-sm text-primary mt-1">Working…</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function ApprovalGate({ run, notes, setNotes, onDecide, busy }) {
  const proposal = run.proposal || {};
  const shifts = proposal.budget_shifts || [];
  const current = proposal.total_budget_current_inr || 0;
  const proposed = proposal.total_budget_proposed_inr || 0;
  const delta = proposed - current;
  const names = Object.fromEntries(
    (proposal.analyst_findings?.per_campaign || []).map((c) => [c.campaign_id, c.campaign_name]),
  );

  return (
    <section className="card overflow-hidden border-amber-300">
      <header className="px-5 py-4 bg-amber-50 border-b border-amber-200 flex items-center gap-3">
        <Icon name="how_to_reg" size={22} className="text-amber-700 shrink-0" fill />
        <div className="flex-1 min-w-0">
          <h2 className="font-headline text-headline-md text-amber-900">Your decision is required</h2>
          <p className="text-body-sm text-amber-800/90">
            The pipeline paused here. Nothing reaches an ad platform until you approve.
          </p>
        </div>
      </header>

      <div className="p-5 space-y-5">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Stat label="Budget shifts" value={shifts.length} />
          <Stat label="Current daily total" value={formatINR(current)} />
          <Stat label="Proposed daily total" value={formatINR(proposed)} />
          <Stat
            label="Net change"
            value={`${delta >= 0 ? '+' : ''}${formatINR(delta)}`}
            tone={delta === 0 ? undefined : delta > 0 ? 'good' : 'critical'}
          />
        </div>

        {proposal.compliance_verdict && (
          <div className="flex items-center gap-2.5 p-3 rounded-lg bg-surface-container-low border border-outline-variant/40">
            <Icon
              name={proposal.compliance_verdict.passed ? 'verified_user' : 'gpp_maybe'}
              size={18}
              fill
              className={proposal.compliance_verdict.passed ? 'text-viz-good' : 'text-amber-600'}
            />
            <span className="text-body-sm text-on-surface-variant flex-1">
              SEBI compliance check on the generated creative
            </span>
            <Chip label={proposal.compliance_verdict.status} />
          </div>
        )}

        {shifts.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-outline-variant/40">
            <table className="w-full text-body-sm">
              <thead className="bg-surface-container-low">
                <tr>
                  <th className="px-4 py-2.5 rail-label text-left">Campaign</th>
                  <th className="px-4 py-2.5 rail-label text-right">Current</th>
                  <th className="px-4 py-2.5 rail-label text-right">Proposed</th>
                  <th className="px-4 py-2.5 rail-label text-right">Change</th>
                  <th className="px-4 py-2.5 rail-label text-left">Rationale</th>
                </tr>
              </thead>
              <tbody>
                {shifts.map((shift) => (
                  <tr
                    key={shift.campaign_id}
                    className="border-t border-outline-variant/25"
                  >
                    <td className="px-4 py-2.5 text-on-surface font-medium">
                      {names[shift.campaign_id] || shift.campaign_id}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-on-surface-variant">
                      {formatINR(shift.current_daily_budget_inr)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-on-surface-variant">
                      {formatINR(shift.proposed_daily_budget_inr)}
                    </td>
                    <td
                      className={`px-4 py-2.5 text-right tabular-nums font-semibold ${
                        shift.shift_percentage >= 0 ? 'text-viz-good' : 'text-viz-critical'
                      }`}
                    >
                      {shift.shift_percentage >= 0 ? '+' : ''}
                      {shift.shift_percentage}%
                    </td>
                    <td className="px-4 py-2.5 text-on-surface-variant">{shift.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <label className="block">
          <span className="rail-label block mb-1.5">Decision notes (recorded in the audit trail)</span>
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={2}
            className="w-full resize-none rounded-lg border border-outline-variant/50 bg-surface-container-lowest px-3.5 py-2.5 text-body-sm focus-ring focus:border-primary/50"
            placeholder="Optional — why you approved or rejected this"
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <Button variant="success" icon="check_circle" disabled={busy} onClick={() => onDecide('approved', notes)}>
            Approve and dispatch
          </Button>
          <Button variant="danger" icon="cancel" disabled={busy} onClick={() => onDecide('rejected', notes)}>
            Reject
          </Button>
        </div>
      </div>
    </section>
  );
}

function Outcome({ run }) {
  const results = run.execution_results || [];
  const ok = results.filter((r) => r.success).length;
  const approved = run.status === 'completed';

  return (
    <section className="card p-5">
      <div className="flex items-center gap-3 mb-4">
        <Icon
          name={approved ? 'task_alt' : 'cancel'}
          size={22}
          fill
          className={approved ? 'text-viz-good' : 'text-outline'}
        />
        <h2 className="font-headline text-headline-md text-on-surface flex-1">
          {approved ? 'Approved and dispatched' : 'Rejected — nothing was dispatched'}
        </h2>
        <Chip label={run.status} />
      </div>

      {run.decision_notes && (
        <p className="text-body-sm text-on-surface-variant mb-4 p-3 rounded-lg bg-surface-container-low">
          <span className="rail-label block mb-1">Your note</span>
          {run.decision_notes}
        </p>
      )}

      {results.length > 0 && (
        <>
          <p className="text-body-sm text-on-surface-variant mb-3">
            {ok} of {results.length} operations succeeded
            {results[0]?.dry_run ? ' (dry run — payloads validated, nothing sent)' : ''}.
          </p>
          <ul className="space-y-1.5">
            {results.map((result, index) => (
              <li
                key={index}
                className="flex items-center gap-2.5 p-2.5 rounded-lg bg-surface-container-low text-body-sm"
              >
                <Icon
                  name={result.success ? 'check_circle' : 'error'}
                  size={16}
                  fill
                  className={result.success ? 'text-viz-good' : 'text-error'}
                />
                <span className="font-mono text-[11px] text-on-surface-variant">
                  {result.action_type}
                </span>
                <span className="text-outline truncate flex-1">{result.resource_id}</span>
                {result.dry_run && <Chip label="dry run" />}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function Stat({ label, value, tone }) {
  const tones = { good: 'text-viz-good', critical: 'text-viz-critical' };
  return (
    <div className="rounded-lg bg-surface-container-low p-3.5">
      <p className="rail-label mb-1">{label}</p>
      <p className={`font-headline text-headline-md tabular-nums ${tones[tone] || 'text-on-surface'}`}>
        {value}
      </p>
    </div>
  );
}
