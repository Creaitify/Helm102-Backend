import React, { useState, useEffect } from 'react';
import { useHelmStore } from '../../context/HelmStore';
import { Play, CheckCircle2, XCircle, AlertTriangle, ArrowRight, Radio } from 'lucide-react';

const RELAY_NODES = [
  { index: 0, title: 'Governor Ingress', meta: 'Classifies task & orchestrates flow' },
  { index: 1, title: 'Ad-Ops Analyst Worker', meta: 'Queries Google & Meta metrics, detects decay' },
  { index: 2, title: 'Creative Studio Worker', meta: 'Brief -> Video Script -> Creative -> Captions' },
  { index: 3, title: 'SEBI Compliance Engine', meta: 'Deterministic statutory rule gate & citations' },
  { index: 4, title: 'Budget Optimizer', meta: '±25% shift cap & conservation check' },
  { index: 5, title: 'Human-in-the-Loop Gate', meta: 'Checkpoint saved · Awaiting approval' },
];

function fmtSeconds(ms) {
  if (ms == null || Number.isNaN(ms) || ms < 0) return '';
  return `${(ms / 1000).toFixed(1)}s`;
}

export function GovernorWorkspace() {
  const {
    startMission,
    isOrchestrating,
    currentRunState,
    recentRuns,
    loadRun,
    clearActiveRun,
    setActiveTab,
    resolveApproval,
    liveMode,
  } = useHelmStore();
  const [objective, setObjective] = useState(
    'Reduce cost per acquisition on SIP growth campaigns and scale top performing search ads.'
  );
  // 300ms ticker while a run is live so elapsed clocks advance smoothly.
  const [now, setNow] = useState(() => Date.now());

  const hops = currentRunState?.hops || [];
  const status = currentRunState?.status || 'idle';
  const proposal = currentRunState?.proposal;

  useEffect(() => {
    if (status !== 'running') return undefined;
    const t = setInterval(() => setNow(Date.now()), 300);
    return () => clearInterval(t);
  }, [status]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!objective.trim()) return;
    startMission(objective.trim());
  };

  // Per-hop wall-clock durations from the envelope timestamps the Governor
  // stamps on every handoff. Hop N's duration = ts[N] - ts[N-1].
  const hopTime = (idx) => {
    const hop = hops.find((h) => h.hop_index === idx);
    return hop?.timestamp ? Date.parse(hop.timestamp) : null;
  };

  const hopDuration = (idx) => {
    const end = hopTime(idx);
    if (end == null) return null;
    const start = idx === 0 ? end : hopTime(idx - 1);
    return start == null ? null : end - start;
  };

  const runStartMs = hopTime(0);
  const lastHopMs = hops.length ? hopTime(hops[hops.length - 1].hop_index) : null;
  const elapsedMs =
    status === 'running' && runStartMs != null
      ? now - runStartMs
      : runStartMs != null && lastHopMs != null
      ? lastHopMs - runStartMs
      : null;

  const getNodeState = (idx) => {
    const hop = hops.find((h) => h.hop_index === idx);
    if (hop) {
      const dur = hopDuration(idx);
      const suffix = dur != null && dur >= 100 ? ` · ${fmtSeconds(dur)}` : '';
      if (hop.status === 'success') return { kind: 'done', text: `Passed ✓${suffix}` };
      if (hop.status === 'degraded') return { kind: 'degraded', text: `Degraded ⚠${suffix}` };
      if (hop.status === 'failed') return { kind: 'failed', text: `Failed ✗${suffix}` };
    }
    if (status === 'running' && hops.length === idx) {
      const thinkingMs = lastHopMs != null ? now - lastHopMs : null;
      return {
        kind: 'thinking',
        text: thinkingMs != null && thinkingMs > 400 ? `Thinking… ${fmtSeconds(thinkingMs)}` : 'Thinking…',
      };
    }
    if (status === 'pending_approval' && idx === 5) {
      return { kind: 'thinking', text: 'Locked (HITL Approval)' };
    }
    return { kind: 'idle', text: 'Pending' };
  };

  return (
    <div className="screen-layout grid-2col">
      {/* Left: Mission Launcher */}
      <div className="card panel-launcher">
        <div className="panel-header">
          <h2 className="panel-heading">Governor Mission Control</h2>
          <span className="panel-tag">Star Coordinator</span>
        </div>
        <p className="panel-desc">
          Define high-level marketing objectives. The Governor classifies the task and coordinates
          specialized workers to produce a governed proposal.
        </p>

        <form onSubmit={handleSubmit} className="mission-form">
          <div className="form-group">
            <label htmlFor="objective-input" className="form-label">
              Marketing Objective
            </label>
            <textarea
              id="objective-input"
              className="form-textarea"
              rows={3}
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="e.g. Reduce cost per acquisition on SIP growth campaigns..."
            />
          </div>

          <div className="quick-presets">
            <span className="preset-label">Quick Scenarios:</span>
            <button
              type="button"
              className="preset-btn"
              onClick={() =>
                setObjective('Reduce CPA on SIP retargeting and scale winning search angles')
              }
            >
              SIP Optimization
            </button>
            <button
              type="button"
              className="preset-btn"
              onClick={() =>
                setObjective('Refresh fatigued Gold ETF creatives and reallocate budget to top ROAS')
              }
            >
              Creative Refresh
            </button>
            <button
              type="button"
              className="preset-btn"
              onClick={() =>
                setObjective('Expand Mutual Fund awareness with compliant high-intent search copy')
              }
            >
              Search Scale
            </button>
          </div>

          <div className="form-actions" style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
            <button
              type="submit"
              disabled={isOrchestrating}
              className="btn btn-primary"
              style={{ flex: 1 }}
            >
              <Play style={{ width: 16, height: 16 }} />
              <span className="btn-text">
                {isOrchestrating ? 'Governor Orchestrating...' : 'Launch Governor Mission'}
              </span>
            </button>

            {currentRunState && (
              <button
                type="button"
                onClick={clearActiveRun}
                className="btn btn-secondary"
                style={{ padding: '0.6rem 0.9rem' }}
                title="Reset active run"
              >
                Reset
              </button>
            )}
          </div>
        </form>

        {/* Human In The Loop Gate Alert if pending */}
        {status === 'pending_approval' && (
          <div
            style={{
              marginTop: '1.25rem',
              padding: '1rem',
              backgroundColor: 'var(--primary-blue-light)',
              border: '1px solid var(--primary-blue-border)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h4 style={{ fontWeight: 700, color: 'var(--primary-blue)', fontSize: '0.9375rem' }}>
                  Human Approval Gate
                </h4>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  Review proposed creative, budget shifts, and compliance before execution.
                </p>
              </div>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setActiveTab('execution')}
              >
                Inspect & Signoff <ArrowRight style={{ width: 14, height: 14 }} />
              </button>
            </div>
          </div>
        )}

        {/* Recent Runs */}
        <div className="recent-runs-block">
          <h3 className="subheading">Orchestration Run History</h3>
          <div className="recent-runs-list">
            {recentRuns.length === 0 ? (
              <div className="empty-state-hint">No active runs yet. Launch a mission above.</div>
            ) : (
              recentRuns.slice(0, 5).map((r) => (
                <div
                  key={r.run_id}
                  className="run-item"
                  onClick={() => loadRun(r.run_id)}
                >
                  <span className="run-item-id">{r.run_id}</span>
                  <span
                    className={`run-item-status ${
                      r.status === 'completed'
                        ? 'text-green'
                        : r.status === 'rejected' || r.status === 'failed'
                        ? 'text-red'
                        : 'text-amber'
                    }`}
                  >
                    {r.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Right: Star Relay Topology */}
      <div className="card panel-relay">
        <div className="panel-header">
          <h2 className="panel-heading">Star Relay Topology</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {liveMode && (
              <span
                className="panel-tag status-running"
                title={liveMode === 'sse' ? 'Live server-push stream' : 'Live polling'}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
              >
                <Radio style={{ width: 12, height: 12 }} className="live-pulse" />
                LIVE
              </span>
            )}
            {elapsedMs != null && elapsedMs > 400 && (
              <span className="panel-tag status-idle mono">{fmtSeconds(elapsedMs)}</span>
            )}
            <span
              className={`panel-tag ${
                status === 'running'
                  ? 'status-running'
                  : status === 'pending_approval'
                  ? 'status-degraded'
                  : status === 'completed'
                  ? 'status-success'
                  : 'status-idle'
              }`}
            >
              {status.toUpperCase()}
            </span>
          </div>
        </div>
        <p className="panel-desc">
          Inter-agent handoffs route through strictly typed Governor envelopes.
        </p>

        <div className="relay-graph">
          {RELAY_NODES.map((node, i) => {
            const { kind, text } = getNodeState(node.index);
            return (
              <React.Fragment key={node.index}>
                <div className={`node-item ${kind === 'thinking' ? 'active' : kind === 'done' ? 'completed' : ''}`}>
                  <div className="node-icon">{node.index}</div>
                  <div className="node-content">
                    <div className="node-title">{node.title}</div>
                    <div className="node-meta">{node.meta}</div>
                  </div>
                  <div
                    className={`node-status ${
                      kind === 'thinking'
                        ? 'status-running node-thinking'
                        : kind === 'done'
                        ? 'status-success'
                        : kind === 'degraded'
                        ? 'status-degraded'
                        : kind === 'failed'
                        ? 'status-failed'
                        : 'status-idle'
                    }`}
                  >
                    {text}
                  </div>
                </div>
                {i < RELAY_NODES.length - 1 && <div className="node-edge" />}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
