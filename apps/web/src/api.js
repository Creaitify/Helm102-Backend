/**
 * Thin typed-ish wrapper over the HELM REST surface.
 *
 * Every call goes through `request`, so a failed call surfaces the backend's
 * `detail` string rather than a generic "Failed to fetch" — the console shows
 * the operator what actually went wrong.
 */

const BASE = '';

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

async function request(path, { method = 'GET', body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (cause) {
    if (cause.name === 'AbortError') throw cause;
    throw new ApiError('Cannot reach the HELM API. Is the server running?', 0, null);
  }

  const isJson = (response.headers.get('content-type') || '').includes('application/json');
  const payload = isJson ? await response.json().catch(() => null) : await response.text();

  if (!response.ok) {
    const detail =
      (payload && payload.detail) ||
      (typeof payload === 'string' && payload.slice(0, 300)) ||
      `Request failed (${response.status})`;
    throw new ApiError(detail, response.status, payload);
  }
  return payload;
}

export const api = {
  // --- System -------------------------------------------------------
  health: () => request('/api/health'),
  dashboardStats: () => request('/api/dashboard/stats'),
  overview: (days = 30) => request(`/api/dashboard/overview?days=${days}`),

  // --- Chat & agents ------------------------------------------------
  modes: () => request('/api/chat/modes'),
  agents: () => request('/api/agents'),
  sendMessage: ({ prompt, mode, conversationId, grounded }, signal) =>
    request('/api/chat', {
      method: 'POST',
      body: { prompt, mode, conversation_id: conversationId ?? null, grounded },
      signal,
    }),
  invokeAgent: (agentId, { prompt, grounded }, signal) =>
    request(`/api/agents/${agentId}/invoke`, { method: 'POST', body: { prompt, grounded }, signal }),

  // --- Conversations ------------------------------------------------
  listConversations: () => request('/api/conversations'),
  getConversation: (id) => request(`/api/conversations/${id}`),
  createConversation: (title, mode) =>
    request('/api/conversations', { method: 'POST', body: { title, mode } }),
  updateConversation: (id, patch) =>
    request(`/api/conversations/${id}`, { method: 'PATCH', body: patch }),
  deleteConversation: (id) => request(`/api/conversations/${id}`, { method: 'DELETE' }),

  // --- Runs & approvals ---------------------------------------------
  listRuns: () => request('/api/runs'),
  getRun: (id) => request(`/api/runs/${id}`),
  startRun: (objective, wait = false) =>
    request('/api/runs', { method: 'POST', body: { objective, wait } }),
  submitApproval: (runId, decision, notes = '') =>
    request(`/api/runs/${runId}/approval`, {
      method: 'POST',
      body: { decision, decision_notes: notes },
    }),
  runAudit: (runId) => request(`/api/runs/${runId}/audit`),

  // --- Reports ------------------------------------------------------
  listReports: () => request('/api/reports'),
  getReport: (id) => request(`/api/reports/${id}`),
  generateReport: (payload) => request('/api/reports/generate', { method: 'POST', body: payload }),
  deleteReport: (id) => request(`/api/reports/${id}`, { method: 'DELETE' }),
  reportMarkdownUrl: (id) => `${BASE}/api/reports/${id}/markdown?download=true`,
  reportHtmlUrl: (id) => `${BASE}/api/reports/${id}/html?download=true`,
  reportPreviewUrl: (id) => `${BASE}/api/reports/${id}/html?download=false`,

  // --- Data sources -------------------------------------------------
  syntheticScenarios: () => request('/api/synthetic/scenarios'),
  generateSynthetic: (scenario, days) =>
    request('/api/synthetic/generate', { method: 'POST', body: { scenario, days } }),
  currentSynthetic: () => request('/api/synthetic/current'),
  byodSample: () => request('/api/byod/sample'),
  parseByod: (csvContent) =>
    request('/api/byod/parse', { method: 'POST', body: { csv_content: csvContent } }),

  // --- Connections --------------------------------------------------
  connections: () => request('/api/connections'),
  deleteConnection: (platform) => request(`/api/connections/${platform}`, { method: 'DELETE' }),
  verifyConnections: () => request('/api/connections/verify', { method: 'POST' }),
  googleOAuthStart: () => request('/api/oauth/google/start'),
  saveGoogleConnection: (payload) =>
    request('/api/connections/google', { method: 'POST', body: payload }),
  saveMetaConnection: (payload) =>
    request('/api/connections/meta', { method: 'POST', body: payload }),

  verifyCopy: (headline, primaryText) =>
    request('/api/citations/verify', {
      method: 'POST',
      body: { headline, primary_text: primaryText },
    }),
};

export { ApiError };
