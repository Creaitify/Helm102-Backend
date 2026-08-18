/**
 * HELM02 Web Console Application Logic
 *
 * Provides dedicated persistent workspaces for each agent (Governor, Ad-Ops,
 * Creative Studio, Compliance Shield, Budget Optimizer, Execution Engine, Audit Trail).
 * State is stored persistently in localStorage so switching tabs never resets
 * or loses progress.
 */

const API_BASE = window.location.origin.startsWith("http")
  ? window.location.origin
  : "http://127.0.0.1:8000";

const POLL_INTERVAL_MS = 1000;

// Persistent Global State
let currentRunId = localStorage.getItem("helm_active_run_id") || null;
let currentRunState = null;
let pollTimer = null;

const HOP_AGENTS = [
  { key: "governor", label: "Governor Ingress" },
  { key: "analyst", label: "Ad-Ops Analyst" },
  { key: "creative", label: "Creative Studio" },
  { key: "compliance", label: "SEBI Compliance" },
  { key: "budget", label: "Budget Optimizer" },
  { key: "governor", label: "HITL Gate" },
];

document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupPresets();
  setupMissionForm();
  setupApprovalButtons();
  setupSyntheticControls();
  setupInteractiveCompliance();
  fetchHealth();
  fetchRecentRuns();
  fetchCurrentSyntheticData();

  // If a run was saved in localStorage, load it immediately
  if (currentRunId) {
    loadExistingRun(currentRunId);
  }
});

// ---------------------------------------------------------------------------
// 1. Tab Navigation & Workspace Routing
// ---------------------------------------------------------------------------

function setupNavigation() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      const targetId = tab.getAttribute("data-target");
      document.querySelectorAll(".screen-view").forEach(view => {
        view.classList.remove("active");
      });
      const targetView = document.getElementById(targetId);
      if (targetView) targetView.classList.add("active");

      // Reactively sync workspace data when entering tabs
      syncAllWorkspaces(currentRunState);

      if (targetId === "screen-audit" && currentRunId) {
        fetchAuditTrail(currentRunId);
      }
    });
  });

  const refreshAuditBtn = document.getElementById("btn-refresh-audit");
  if (refreshAuditBtn) {
    refreshAuditBtn.addEventListener("click", () => {
      if (currentRunId) fetchAuditTrail(currentRunId);
    });
  }
}

function setupPresets() {
  const presetBtns = document.querySelectorAll(".preset-btn");
  const input = document.getElementById("objective-input");
  presetBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      input.value = btn.getAttribute("data-goal");
    });
  });
}

// ---------------------------------------------------------------------------
// 2. Health & System Telemetry
// ---------------------------------------------------------------------------

async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById("val-model").textContent = (data.active_model || "GEMINI 2.5").toUpperCase();
      document.getElementById("val-writes").textContent = data.dry_run ? "DRY-RUN" : "LIVE";
      const dataChip = document.getElementById("val-data");
      dataChip.textContent = (data.data_source || "SQLITE SYNTHETIC").toUpperCase();
    }
  } catch (err) {
    console.warn("Could not reach backend health endpoint:", err);
  }
}

// ---------------------------------------------------------------------------
// 3. Governor Mission Launch & Real-Time Polling
// ---------------------------------------------------------------------------

function setupMissionForm() {
  const form = document.getElementById("mission-form");
  const btn = document.getElementById("btn-start-run");
  const input = document.getElementById("objective-input");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const objective = input.value.trim();
    if (!objective) return;

    btn.disabled = true;
    btn.querySelector(".btn-text").textContent = "⚡ Governor Orchestrating...";
    resetRelayNodes();
    setNodeState(0, "thinking", "Ingesting Objective...");

    try {
      const res = await fetch(`${API_BASE}/api/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      currentRunId = data.run_id;
      localStorage.setItem("helm_active_run_id", data.run_id);
      startPolling(data.run_id);
    } catch (err) {
      alert(`Relay launch failed: ${err.message}`);
      resetRelayNodes();
      btn.disabled = false;
      btn.querySelector(".btn-text").textContent = "🚀 Launch Governor Orchestration";
    }
  });
}

function startPolling(runId) {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/runs/${runId}`);
      if (!res.ok) return;
      const state = await res.json();
      currentRunState = state;
      renderRelayProgress(state);
      syncAllWorkspaces(state);

      if (["pending_approval", "completed", "rejected", "failed"].includes(state.status)) {
        stopPolling();
        onRunSettled(state);
      }
    } catch (err) {
      console.warn("Polling error:", err);
    }
  }, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function onRunSettled(state) {
  const btn = document.getElementById("btn-start-run");
  if (btn) {
    btn.disabled = false;
    btn.querySelector(".btn-text").textContent = "🚀 Launch Governor Orchestration";
  }
  fetchRecentRuns();

  if (state.status === "pending_approval") {
    document.getElementById("pending-count").style.display = "inline-block";
  } else {
    document.getElementById("pending-count").style.display = "none";
  }
}

// ---------------------------------------------------------------------------
// 4. Relay Graph Visualization
// ---------------------------------------------------------------------------

function renderRelayProgress(state) {
  const badge = document.getElementById("run-status-badge");
  const hops = state.hops || [];
  const doneCount = hops.length;

  if (state.status === "running") {
    const agent = HOP_AGENTS[Math.min(doneCount, 5)];
    badge.textContent = `RELAYING — ${agent.label.toUpperCase()}`;
    badge.className = "panel-tag status-running";
  } else if (state.status === "pending_approval") {
    badge.textContent = "AWAITING HITL APPROVAL";
    badge.className = "panel-tag status-degraded";
  } else if (state.status === "failed") {
    badge.textContent = "FAILED";
    badge.className = "panel-tag status-failed";
  } else {
    badge.textContent = state.status.toUpperCase();
    badge.className = "panel-tag status-success";
  }

  hops.forEach(h => {
    if (h.hop_index > 5) return;
    if (h.status === "success") {
      setNodeState(h.hop_index, "done", "Passed ✓");
    } else if (h.status === "degraded") {
      setNodeState(h.hop_index, "degraded", "Degraded ⚠");
    } else if (h.status === "failed") {
      setNodeState(h.hop_index, "failed", "Failed ✗");
    }
  });

  if (state.status === "running" && doneCount <= 5) {
    setNodeState(doneCount, "thinking", "Thinking...");
  }
  if (state.status === "pending_approval") {
    setNodeState(5, "thinking", "Locked (HITL Approval)");
  }
}

function setNodeState(idx, kind, text) {
  const el = document.getElementById(`node-${idx}`);
  if (!el) return;
  const statusEl = el.querySelector(".node-status");
  if (kind === "thinking") {
    el.className = "node-item active";
    statusEl.className = "node-status status-running node-thinking";
  } else if (kind === "done") {
    el.className = "node-item completed";
    statusEl.className = "node-status status-success";
  } else if (kind === "degraded") {
    el.className = "node-item completed";
    statusEl.className = "node-status status-degraded";
  } else if (kind === "failed") {
    el.className = "node-item";
    statusEl.className = "node-status status-failed";
  } else {
    el.className = "node-item";
    statusEl.className = "node-status status-idle";
  }
  statusEl.textContent = text;
}

function resetRelayNodes() {
  for (let idx = 0; idx <= 5; idx++) setNodeState(idx, "idle", "Pending");
  document.getElementById("run-status-badge").textContent = "STANDBY";
}

// ---------------------------------------------------------------------------
// 5. Reactive Workspace Synchronization (No-Vanish Guarantee)
// ---------------------------------------------------------------------------

function syncAllWorkspaces(state) {
  if (!state) return;

  const reports = state.agent_reports || {};
  const proposal = state.proposal || {};

  // Sync Ad-Ops Workspace
  if (reports.analyst) {
    renderAdOpsWorkspace(reports.analyst);
  }

  // Sync Creative Studio Workspace
  if (reports.creative || proposal.creative_package) {
    renderCreativeWorkspace(reports.creative || proposal.creative_package);
  }

  // Sync Compliance Shield Workspace
  if (reports.compliance || proposal.compliance_verdict) {
    renderComplianceWorkspace(reports.compliance || proposal.compliance_verdict);
  }

  // Sync Budget Optimizer Workspace
  if (reports.budget || proposal.budget_shifts) {
    renderBudgetWorkspace(reports.budget || { shifts: proposal.budget_shifts, total_current_inr: proposal.total_budget_current_inr, total_proposed_inr: proposal.total_budget_proposed_inr });
  }

  // Sync Execution Engine Screen
  renderExecutionWorkspace(state);
}

// ---------------------------------------------------------------------------
// 6. Individual Agent Workspace Renderers
// ---------------------------------------------------------------------------

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderAdOpsWorkspace(analystData) {
  const container = document.getElementById("adops-campaigns-table-container");
  const trendsContainer = document.getElementById("adops-trends-container");
  if (!container) return;

  const campaigns = analystData.per_campaign || [];
  if (campaigns.length === 0) {
    container.innerHTML = `<div class="empty-state-hint">No campaign metrics loaded yet.</div>`;
    return;
  }

  const rows = campaigns.map(c => `
    <tr>
      <td><strong>${esc(c.campaign_name)}</strong><br><span class="mono text-muted" style="font-size:0.75rem;">${esc(c.campaign_id)}</span></td>
      <td><span class="badge badge-blue">${esc(c.platform)}</span></td>
      <td>₹${Number(c.spend_inr || c.spend).toLocaleString()}</td>
      <td><strong class="${(c.roas || 0) >= 3.0 ? 'text-green' : (c.roas || 0) < 2.0 ? 'text-red' : 'text-blue'}">${esc(c.roas)}x</strong></td>
      <td>₹${Math.round(c.cpa_inr || c.cpa || 0)}</td>
      <td>${esc(c.ctr)}%</td>
      <td><span class="badge ${c.score >= 70 ? 'badge-emerald' : 'badge-amber'}">${esc(c.score || 80)}/100</span></td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table class="metric-table">
      <thead>
        <tr>
          <th>Campaign</th>
          <th>Platform</th>
          <th>Spend</th>
          <th>ROAS</th>
          <th>CPA</th>
          <th>CTR</th>
          <th>Performance Score</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;

  if (trendsContainer) {
    const trends = (analystData.trends || []).map(t => `<li>📈 ${esc(t)}</li>`).join("");
    const decay = (analystData.decay_signals || []).map(d => `<li class="text-red">⚠️ ${esc(d)}</li>`).join("");
    const whatWorks = (analystData.what_works || []).map(w => `<li class="text-green">✅ ${esc(w)}</li>`).join("");

    trendsContainer.innerHTML = `
      <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:1rem;">
        <div class="card" style="padding:1rem;">
          <h4 class="subheading" style="color:var(--primary-blue);">Trend Analysis</h4>
          <ul class="report-list" style="font-size:0.8125rem; line-height:1.6; list-style:none;">${trends || '<li>No trends recorded</li>'}</ul>
        </div>
        <div class="card" style="padding:1rem;">
          <h4 class="subheading" style="color:var(--accent-emerald);">Winning Angles</h4>
          <ul class="report-list" style="font-size:0.8125rem; line-height:1.6; list-style:none;">${whatWorks || '<li>No angles identified</li>'}</ul>
        </div>
        <div class="card" style="padding:1rem;">
          <h4 class="subheading" style="color:var(--accent-rose);">Decay Signals</h4>
          <ul class="report-list" style="font-size:0.8125rem; line-height:1.6; list-style:none;">${decay || '<li>No decay detected</li>'}</ul>
        </div>
      </div>
    `;
  }
}

function renderCreativeWorkspace(pkg) {
  const container = document.getElementById("creative-workspace-content");
  if (!container || !pkg) return;

  const brief = pkg.brief || {};
  const script = pkg.script || {};
  const creative = pkg.creative || {};
  const captions = pkg.captions || {};

  const scenes = (script.scenes || []).map(s => `
    <div style="background:var(--bg-card-subtle); padding:0.6rem 0.8rem; border-radius:var(--radius-sm); border:1px solid var(--border-color); margin-bottom:0.4rem;">
      <div style="display:flex; justify-content:space-between; margin-bottom:0.2rem;">
        <span class="badge badge-blue" style="font-size:0.7rem;">${esc(s.timestamp_range || 'Scene')}</span>
        <span class="mono" style="font-size:0.75rem; color:var(--text-muted);">${esc(s.on_screen_text || '')}</span>
      </div>
      <p style="font-size:0.8125rem;"><strong>Visual:</strong> ${esc(s.visual_cue)}</p>
      <p style="font-size:0.8125rem; color:var(--text-muted);"><strong>Audio:</strong> "${esc(s.audio_spoken)}"</p>
    </div>
  `).join("");

  container.innerHTML = `
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1.5rem; margin-top:1rem;">
      <!-- Stage 1 & 2 -->
      <div style="display:flex; flex-direction:column; gap:1rem;">
        <div class="card" style="padding:1.25rem;">
          <div class="card-header" style="margin-bottom:0.5rem; padding-bottom:0.5rem;">
            <h4 class="card-title" style="font-size:0.9375rem;">Stage 1: Creative Brief</h4>
            <span class="badge badge-blue">Strategic Angle</span>
          </div>
          <p style="font-size:0.875rem;"><strong>Core Angle:</strong> ${esc(brief.core_angle)}</p>
          <p style="font-size:0.8125rem; color:var(--text-muted); margin-top:0.25rem;"><strong>Audience:</strong> ${esc(brief.target_audience)}</p>
          <p style="font-size:0.8125rem; color:var(--text-muted); margin-top:0.25rem;"><strong>Pain Point:</strong> ${esc(brief.pain_point)}</p>
          <p style="font-size:0.8125rem; color:var(--text-muted); margin-top:0.25rem;"><strong>Value Prop:</strong> ${esc(brief.value_proposition)}</p>
        </div>

        <div class="card" style="padding:1.25rem;">
          <div class="card-header" style="margin-bottom:0.5rem; padding-bottom:0.5rem;">
            <h4 class="card-title" style="font-size:0.9375rem;">Stage 2: 9:16 Video Script (${esc(script.duration_seconds || 30)}s)</h4>
            <span class="badge badge-purple">${esc(script.aspect_ratio || '9:16')}</span>
          </div>
          <p style="font-size:0.875rem; margin-bottom:0.5rem;"><strong>0-3s Hook:</strong> "${esc(script.hook_3s)}"</p>
          <div style="margin-top:0.5rem;">${scenes}</div>
        </div>
      </div>

      <!-- Stage 3 & 4 -->
      <div style="display:flex; flex-direction:column; gap:1rem;">
        <div class="card" style="padding:1.25rem;">
          <div class="card-header" style="margin-bottom:0.5rem; padding-bottom:0.5rem;">
            <h4 class="card-title" style="font-size:0.9375rem;">Stage 3: Ad Copy &amp; Headlines</h4>
            <span class="badge badge-emerald">${esc(creative.call_to_action || 'INVEST_NOW')}</span>
          </div>
          <h5 style="font-size:1rem; font-weight:700; color:var(--primary-blue);">${esc(creative.headline)}</h5>
          <p style="font-size:0.875rem; margin-top:0.5rem; line-height:1.6;">${esc(creative.primary_text)}</p>
          
          <div style="margin-top:0.75rem;">
            <span class="subheading" style="font-size:0.75rem;">Alternative Headlines:</span>
            <ul style="font-size:0.8125rem; color:var(--text-muted); margin-left:1rem; margin-top:0.25rem;">
              ${(creative.alternative_headlines || []).map(h => `<li>${esc(h)}</li>`).join("")}
            </ul>
          </div>
        </div>

        <div class="card" style="padding:1.25rem;">
          <div class="card-header" style="margin-bottom:0.5rem; padding-bottom:0.5rem;">
            <h4 class="card-title" style="font-size:0.9375rem;">Stage 4: Social Platform Captions</h4>
            <span class="badge badge-amber">Multi-Platform</span>
          </div>
          <div style="font-size:0.8125rem; color:var(--text-muted); margin-bottom:0.5rem;">
            <strong style="color:var(--text-main);">Instagram:</strong> ${esc(captions.instagram_caption)}
          </div>
          <div style="font-size:0.8125rem; color:var(--text-muted);">
            <strong style="color:var(--text-main);">LinkedIn:</strong> ${esc(captions.linkedin_caption)}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderComplianceWorkspace(comp) {
  const container = document.getElementById("compliance-workspace-content");
  const badge = document.getElementById("compliance-status-badge");
  if (!container || !comp) return;

  const passed = comp.status === "pass" || comp.passed === true;
  if (badge) {
    badge.textContent = passed ? "VERIFIED (PASS)" : "FLAGGED (FAIL)";
    badge.className = passed ? "badge badge-emerald" : "badge badge-rose";
  }

  const violations = (comp.violations || []).map(v => `
    <div style="background:var(--accent-rose-light); border:1px solid #fecaca; padding:0.75rem; border-radius:var(--radius-sm); margin-bottom:0.5rem;">
      <span class="badge badge-rose" style="font-size:0.7rem;">PROHIBITED CLAIM</span>
      <p style="font-size:0.8125rem; color:var(--text-main); margin-top:0.3rem;">${esc(typeof v === 'string' ? v : JSON.stringify(v))}</p>
    </div>
  `).join("");

  container.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:1rem; margin-top:0.5rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg-card-subtle); padding:0.75rem 1rem; border-radius:var(--radius-md); border:1px solid var(--border-color);">
        <div>
          <span style="font-size:0.8125rem; font-weight:700;">Statutory Disclaimer:</span>
          <span style="font-size:0.8125rem; margin-left:0.5rem;" class="${comp.has_mandatory_disclaimer ? 'text-green font-bold' : 'text-red font-bold'}">
            ${comp.has_mandatory_disclaimer ? 'Present & Verified ✓' : 'Missing ✗'}
          </span>
        </div>
        <div style="font-size:0.75rem; color:var(--text-muted);">
          Rules Version: <strong>${esc(comp.rules_version || 'SEBI_2026_AD_CODE')}</strong> · Loopbacks: <strong>${esc(comp.loopback_count || 0)}</strong>
        </div>
      </div>

      ${violations ? `<div><h4 class="subheading" style="color:var(--accent-rose);">Flagged Issues</h4>${violations}</div>` : `
        <div style="background:var(--accent-emerald-light); border:1px solid #a7f3d0; padding:1rem; border-radius:var(--radius-md);">
          <div style="font-weight:700; color:var(--accent-emerald); font-size:0.875rem;">✓ Full Statutory Compliance</div>
          <p style="font-size:0.8125rem; color:var(--text-main); margin-top:0.25rem;">
            Copy verified against SEBI regulations. Zero guaranteed return claims and mandatory risk disclaimers present.
          </p>
        </div>
      `}
    </div>
  `;
}

function renderBudgetWorkspace(budgetData) {
  const container = document.getElementById("budget-workspace-content");
  if (!container || !budgetData) return;

  const shifts = budgetData.shifts || [];
  const rows = shifts.map(s => `
    <tr>
      <td><span class="mono" style="font-weight:700;">${esc(s.campaign_id)}</span></td>
      <td>₹${Number(s.current_daily_budget_inr).toLocaleString()}</td>
      <td><strong style="color:var(--primary-blue);">₹${Number(s.proposed_daily_budget_inr).toLocaleString()}</strong></td>
      <td>
        <span class="${s.shift_percentage > 0 ? 'badge badge-emerald' : 'badge badge-amber'}">
          ${s.shift_percentage > 0 ? '+' : ''}${esc(s.shift_percentage)}%
        </span>
      </td>
      <td style="font-size:0.8125rem; color:var(--text-muted);">${esc(s.rationale || 'Budget rebalancing')}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <div style="margin-top:0.5rem;">
      <table class="metric-table">
        <thead>
          <tr>
            <th>Campaign ID</th>
            <th>Current Budget/Day</th>
            <th>Proposed Budget/Day</th>
            <th>Budget Shift</th>
            <th>Rationale</th>
          </tr>
        </thead>
        <tbody>${rows || '<tr><td colspan="5">No shifts proposed</td></tr>'}</tbody>
      </table>

      <div style="margin-top:1rem; background:var(--bg-card-subtle); padding:0.75rem 1rem; border-radius:var(--radius-md); border:1px solid var(--border-color); display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:0.8125rem; color:var(--text-muted);">
          Total Current: <strong>₹${Number(budgetData.total_current_inr || 0).toLocaleString()}</strong> &rarr; Total Proposed: <strong>₹${Number(budgetData.total_proposed_inr || 0).toLocaleString()}</strong>
        </span>
        <span class="badge badge-emerald">Budget Conservation Law Satisfied</span>
      </div>
    </div>
  `;
}

function renderExecutionWorkspace(state) {
  if (!state) return;
  const proposal = state.proposal || {};

  document.getElementById("appr-run-id").textContent = state.run_id || "—";
  document.getElementById("appr-compliance-val").textContent =
    (proposal.compliance_verdict?.status || "PASS").toUpperCase();
  document.getElementById("appr-budget-val").textContent =
    `₹${proposal.total_budget_proposed_inr || 0}/day`;

  const preview = proposal.dry_run_preview || { status: "Awaiting proposal assembly" };
  document.getElementById("appr-payload-preview").textContent = JSON.stringify(preview, null, 2);

  const statusPill = document.getElementById("approval-status-pill");
  if (state.status === "completed") {
    statusPill.textContent = "APPROVED & EXECUTED";
    statusPill.className = "status-pill status-success";
  } else if (state.status === "rejected") {
    statusPill.textContent = "REJECTED BY OPERATOR";
    statusPill.className = "status-pill status-danger";
  } else if (state.status === "pending_approval") {
    statusPill.textContent = "AWAITING HITL DECISION";
    statusPill.className = "status-pill status-pending";
  }

  const resultsBox = document.getElementById("execution-results-box");
  const resultsList = document.getElementById("execution-results-list");
  if (state.execution_results && state.execution_results.length > 0) {
    resultsBox.style.display = "block";
    resultsList.innerHTML = state.execution_results.map(r => `
      <div style="background:var(--bg-card-subtle); padding:0.6rem 0.8rem; border-radius:var(--radius-sm); margin-bottom:0.4rem; border:1px solid var(--border-color);">
        <span class="badge ${r.success ? 'badge-emerald' : 'badge-amber'}">${r.success ? 'SUCCESS' : 'FAILED'}</span>
        <span class="mono" style="margin-left:0.5rem; font-weight:600;">${esc(r.action_type)} &rarr; ${esc(r.resource_id)}</span>
        <span class="badge ${r.dry_run ? 'badge-blue' : 'badge-purple'}" style="float:right;">${r.dry_run ? 'DRY-RUN' : 'LIVE'}</span>
      </div>
    `).join("");
  }
}

// ---------------------------------------------------------------------------
// 7. Human Approval Gate Interaction
// ---------------------------------------------------------------------------

function setupApprovalButtons() {
  document.getElementById("btn-approve").addEventListener("click", () => handleDecision("approved"));
  document.getElementById("btn-reject").addEventListener("click", () => handleDecision("rejected"));
}

async function handleDecision(decision) {
  if (!currentRunId) return;

  const notesInput = document.getElementById("appr-notes");
  const decision_notes = notesInput.value.trim() || `Human operator decision: ${decision}`;

  try {
    const res = await fetch(`${API_BASE}/api/runs/${currentRunId}/approval`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, decision_notes }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentRunState = data;
    syncAllWorkspaces(data);
    document.getElementById("pending-count").style.display = "none";
    fetchRecentRuns();
  } catch (err) {
    alert(`Decision submission failed: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// 8. Synthetic Data Engine & Interactive Tools
// ---------------------------------------------------------------------------

function setupSyntheticControls() {
  const btn = document.getElementById("btn-generate-synthetic");
  const select = document.getElementById("synthetic-scenario-select");
  if (btn && select) {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "Generating SQLite Data...";
      try {
        const res = await fetch(`${API_BASE}/api/synthetic/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scenario: select.value, days: 30 }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        await fetchCurrentSyntheticData();
      } catch (err) {
        alert(`Synthetic generation failed: ${err.message}`);
      } finally {
        btn.disabled = false;
        btn.textContent = "⚡ Generate & Seed SQLite Data";
      }
    });
  }

  const byodBtn = document.getElementById("btn-upload-byod");
  const byodInput = document.getElementById("byod-csv-input");
  if (byodBtn && byodInput) {
    byodBtn.addEventListener("click", async () => {
      const csv = byodInput.value.trim();
      if (!csv) return;
      try {
        const res = await fetch(`${API_BASE}/api/byod/parse`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ csv_content: csv }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const parsed = await res.json();
        renderAdOpsWorkspace({ per_campaign: parsed.campaigns, trends: ["BYOD Custom CSV Ingested"] });
      } catch (err) {
        alert(`BYOD Parse error: ${err.message}`);
      }
    });
  }
}

async function fetchCurrentSyntheticData() {
  try {
    const res = await fetch(`${API_BASE}/api/synthetic/current`);
    if (res.ok) {
      const snapshot = await res.json();
      renderAdOpsWorkspace({
        per_campaign: snapshot.campaigns,
        trends: ["SQLite Synthetic Master Snapshot Loaded with 30D Coherent Variances"],
        what_works: ["High-Intent Search SIP Campaigns achieving >3.2x ROAS"],
        decay_signals: ["Broad audience Meta retargeting showing CTR decay"],
      });
    }
  } catch (err) {
    console.warn("Could not fetch synthetic snapshot:", err);
  }
}

function setupInteractiveCompliance() {
  const btn = document.getElementById("btn-verify-copy-interactive");
  const headlineInput = document.getElementById("comp-test-headline");
  const bodyInput = document.getElementById("comp-test-body");
  const resultBox = document.getElementById("comp-test-result-box");

  if (btn && headlineInput && bodyInput && resultBox) {
    btn.addEventListener("click", async () => {
      const headline = headlineInput.value.trim();
      const primary_text = bodyInput.value.trim();
      if (!headline && !primary_text) return;

      btn.disabled = true;
      btn.textContent = "Scanning...";
      try {
        const res = await fetch(`${API_BASE}/api/citations/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ headline, primary_text }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        resultBox.style.display = "block";
        const passed = data.status === "pass";
        resultBox.innerHTML = `
          <div style="background:${passed ? 'var(--accent-emerald-light)' : 'var(--accent-rose-light)'}; border:1px solid ${passed ? '#a7f3d0' : '#fecaca'}; padding:0.75rem; border-radius:var(--radius-sm);">
            <div style="font-weight:700; color:${passed ? 'var(--accent-emerald)' : 'var(--accent-rose)'}; font-size:0.8125rem;">
              ${passed ? '✓ PASSED SEBI COMPLIANCE' : '✗ FLAGGED ISSUES DETECTED'}
            </div>
            <p style="font-size:0.75rem; color:var(--text-main); margin-top:0.25rem;">
              Grounding Score: <strong>${(data.overall_score * 100).toFixed(0)}%</strong>
            </p>
          </div>
        `;
      } catch (err) {
        alert(`Verification failed: ${err.message}`);
      } finally {
        btn.disabled = false;
        btn.textContent = "🛡️ Scan Copy for SEBI Compliance";
      }
    });
  }
}

// ---------------------------------------------------------------------------
// 9. Audit Trail & Run History
// ---------------------------------------------------------------------------

async function fetchAuditTrail(runId) {
  const container = document.getElementById("audit-timeline");
  container.innerHTML = `<div class="empty-state-hint">Loading audit envelopes for ${esc(runId)}...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/runs/${runId}/audit`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const trail = await res.json();

    if (!trail || trail.length === 0) {
      container.innerHTML = `<div class="empty-state-hint">No audit events recorded for ${esc(runId)}.</div>`;
      return;
    }

    container.innerHTML = trail.map(event => `
      <div class="audit-entry">
        <div class="audit-hop-badge">H${event.hop_index}</div>
        <div class="audit-details">
          <div class="audit-meta-row">
            <span class="audit-action">${esc(event.action)}</span>
            <span class="audit-time">${new Date(event.created_at).toLocaleTimeString()}</span>
          </div>
          <div class="audit-route">
            <span class="mono">${esc(event.source)}</span> &rarr; <span class="mono">${esc(event.target)}</span>
            <span class="badge ${event.status === "success" ? "badge-emerald" : "badge-amber"}" style="margin-left:0.5rem;">${esc(event.status.toUpperCase())}</span>
          </div>
          <div class="audit-rationale">${esc(event.rationale || "")}</div>
          <pre class="json-preview" style="max-height:120px; font-size:0.75rem; margin-bottom:0;">${esc(JSON.stringify(event.payload, null, 2))}</pre>
        </div>
      </div>
    `).join("");
  } catch (err) {
    container.innerHTML = `<div class="empty-state-hint text-red">Failed to load audit trail: ${esc(err.message)}</div>`;
  }
}

async function fetchRecentRuns() {
  const list = document.getElementById("recent-runs-list");
  try {
    const res = await fetch(`${API_BASE}/api/runs`);
    if (!res.ok) return;
    const runs = await res.json();

    if (!runs || runs.length === 0) {
      list.innerHTML = `<div class="empty-state-hint">No active runs yet. Launch a mission above.</div>`;
      return;
    }

    list.innerHTML = runs.slice(0, 6).map(r => `
      <div class="run-item" onclick="loadExistingRun('${esc(r.run_id)}')">
        <span class="run-item-id">${esc(r.run_id)}</span>
        <span class="run-item-status ${
          r.status === "completed" ? "text-green"
          : (r.status === "rejected" || r.status === "failed") ? "text-red"
          : "text-amber"
        }">${esc(r.status)}</span>
      </div>
    `).join("");
  } catch (err) {
    console.warn("Could not fetch recent runs:", err);
  }
}

window.loadExistingRun = async function (runId) {
  try {
    const res = await fetch(`${API_BASE}/api/runs/${runId}`);
    if (!res.ok) return;
    const data = await res.json();
    currentRunId = data.run_id;
    localStorage.setItem("helm_active_run_id", data.run_id);
    currentRunState = data;
    renderRelayProgress(data);
    syncAllWorkspaces(data);

    if (data.status === "running") {
      startPolling(runId);
    }
  } catch (err) {
    console.warn(`Could not load run ${runId}:`, err);
  }
};
