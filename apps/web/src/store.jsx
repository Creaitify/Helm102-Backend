/**
 * HelmStore — the platform's single source of truth.
 *
 * Server-owned state (overview, agent output, runs, reports) is fetched and
 * never mirrored into localStorage; only view preferences persist. A refresh
 * must never resurrect a stale answer the server no longer has, and must never
 * lose the operator's place.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from 'react';
import { api } from './api';

const HelmContext = createContext(null);
const PREFS_KEY = 'helm.prefs.v2';

function loadPrefs() {
  try {
    return JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
  } catch {
    return {};
  }
}

/**
 * Built on mount rather than at module load: reading localStorage at import
 * time freezes preferences to whatever the first import saw.
 */
function createInitialState() {
  const prefs = loadPrefs();
  return {
    // Navigation
    screen: prefs.screen || 'overview', // overview | agents | pipeline | reports | data | audit | settings
    activeAgent: prefs.activeAgent || 'analyst',
    sidebarOpen: false,

    // Server data
    health: null,
    overview: null,
    agentRoster: [],

    // Agent consoles — one transcript per agent, held for the session
    agentThreads: {},
    agentBusy: null,

    // Pipeline
    run: null,
    runBusy: false,

    // Transient
    loading: true,
    error: null,
    toast: null,
  };
}

function reducer(state, action) {
  switch (action.type) {
    case 'set':
      return { ...state, ...action.patch };

    case 'agent:append': {
      const existing = state.agentThreads[action.agent] || [];
      return {
        ...state,
        agentThreads: { ...state.agentThreads, [action.agent]: [...existing, ...action.entries] },
      };
    }

    case 'agent:replaceLast': {
      const existing = state.agentThreads[action.agent] || [];
      return {
        ...state,
        agentThreads: {
          ...state.agentThreads,
          [action.agent]: [...existing.slice(0, -1), action.entry],
        },
      };
    }

    case 'agent:clear':
      return { ...state, agentThreads: { ...state.agentThreads, [action.agent]: [] } };

    default:
      return state;
  }
}

export function HelmProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, undefined, createInitialState);
  const pollRef = useRef(null);

  const set = useCallback((patch) => dispatch({ type: 'set', patch }), []);

  useEffect(() => {
    try {
      localStorage.setItem(
        PREFS_KEY,
        JSON.stringify({ screen: state.screen, activeAgent: state.activeAgent }),
      );
    } catch {
      /* private mode — preferences simply won't persist */
    }
  }, [state.screen, state.activeAgent]);

  const refreshOverview = useCallback(async () => {
    try {
      set({ overview: await api.overview(30) });
    } catch (err) {
      set({ error: err.message });
    }
  }, [set]);

  // Boot
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [health, overview, agentRoster] = await Promise.all([
        api.health().catch(() => null),
        api.overview(30).catch(() => null),
        api.agents().catch(() => []),
      ]);
      if (!cancelled) set({ health, overview, agentRoster, loading: false });
    })();
    return () => {
      cancelled = true;
    };
  }, [set]);

  // --- Individual agents -------------------------------------------

  const askAgent = useCallback(
    async (agentId, prompt) => {
      const text = String(prompt || '').trim();
      if (!text || state.agentBusy) return;

      dispatch({
        type: 'agent:append',
        agent: agentId,
        entries: [
          { kind: 'question', text, at: new Date().toISOString() },
          { kind: 'pending', at: new Date().toISOString() },
        ],
      });
      set({ agentBusy: agentId, error: null });

      try {
        const envelope = await api.invokeAgent(agentId, { prompt: text, grounded: true });
        dispatch({
          type: 'agent:replaceLast',
          agent: agentId,
          entry: { kind: 'answer', envelope, at: new Date().toISOString() },
        });
      } catch (err) {
        dispatch({
          type: 'agent:replaceLast',
          agent: agentId,
          entry: { kind: 'error', text: err.message, at: new Date().toISOString() },
        });
      } finally {
        set({ agentBusy: null });
      }
    },
    [state.agentBusy, set],
  );

  const clearAgent = useCallback((agentId) => dispatch({ type: 'agent:clear', agent: agentId }), []);

  // --- Pipeline -----------------------------------------------------

  const startRun = useCallback(
    async (objective) => {
      const text = String(objective || '').trim();
      if (!text || state.runBusy) return;

      set({ runBusy: true, error: null, run: null });
      try {
        const started = await api.startRun(text, false);
        set({ run: { ...started, hops: [], objective: text } });
      } catch (err) {
        set({ runBusy: false, error: err.message });
      }
    },
    [state.runBusy, set],
  );

  const decideRun = useCallback(
    async (decision, notes = '') => {
      const id = state.run?.run_id;
      if (!id) return;
      set({ runBusy: true });
      try {
        const updated = await api.submitApproval(id, decision, notes);
        set({
          run: updated,
          runBusy: false,
          toast: {
            tone: decision === 'approved' ? 'success' : 'warn',
            text:
              decision === 'approved'
                ? 'Approved. Execution dispatched (dry run unless live writes are enabled).'
                : 'Rejected. Nothing was dispatched.',
          },
        });
        refreshOverview();
      } catch (err) {
        set({ runBusy: false, error: err.message });
      }
    },
    [state.run, set, refreshOverview],
  );

  // Poll an in-flight run so the pipeline view advances live. Keyed on
  // id + status only, so each poll result doesn't respawn the interval.
  const runId = state.run?.run_id;
  const runStatus = state.run?.status;
  useEffect(() => {
    clearInterval(pollRef.current);
    if (!runId || !['running', 'interrupted'].includes(runStatus)) return undefined;

    pollRef.current = setInterval(async () => {
      try {
        const fresh = await api.getRun(runId);
        set({ run: fresh, runBusy: fresh.status === 'running' });
      } catch {
        clearInterval(pollRef.current);
        set({ runBusy: false });
      }
    }, 1000);
    return () => clearInterval(pollRef.current);
  }, [runId, runStatus, set]);

  useEffect(() => {
    if (!state.toast) return undefined;
    const timer = setTimeout(() => set({ toast: null }), 5000);
    return () => clearTimeout(timer);
  }, [state.toast, set]);

  const value = useMemo(
    () => ({ ...state, set, refreshOverview, askAgent, clearAgent, startRun, decideRun }),
    [state, set, refreshOverview, askAgent, clearAgent, startRun, decideRun],
  );

  return <HelmContext.Provider value={value}>{children}</HelmContext.Provider>;
}

export function useHelm() {
  const ctx = useContext(HelmContext);
  if (!ctx) throw new Error('useHelm must be used inside <HelmProvider>');
  return ctx;
}
