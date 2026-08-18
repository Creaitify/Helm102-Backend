import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = window.location.origin.startsWith('http')
  ? window.location.origin
  : 'http://127.0.0.1:8000';

const SETTLED = ['pending_approval', 'completed', 'rejected', 'failed'];

const HelmStoreContext = createContext(null);

export function HelmStoreProvider({ children }) {
  const [activeTab, setActiveTab] = useState(() => {
    return localStorage.getItem('helm_active_tab') || 'governor';
  });
  const [currentRunId, setCurrentRunId] = useState(() => {
    return localStorage.getItem('helm_active_run_id') || null;
  });
  const [currentRunState, setCurrentRunState] = useState(() => {
    try {
      const saved = localStorage.getItem('helm_active_run_state');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [health, setHealth] = useState({
    active_model: 'gemini-2.5-flash',
    gateway_mode: 'live',
    data_source: 'synthetic',
    dry_run: true,
  });
  const [recentRuns, setRecentRuns] = useState([]);
  const [syntheticSnapshot, setSyntheticSnapshot] = useState(null);
  const [isOrchestrating, setIsOrchestrating] = useState(false);
  // 'sse' while an EventSource is attached, 'poll' when falling back, null when idle.
  const [liveMode, setLiveMode] = useState(null);

  // Live-stream plumbing: exactly one active subscription at a time.
  const eventSourceRef = useRef(null);
  const pollTimerRef = useRef(null);

  // Persist tab & run state
  useEffect(() => {
    localStorage.setItem('helm_active_tab', activeTab);
  }, [activeTab]);

  useEffect(() => {
    if (currentRunId) {
      localStorage.setItem('helm_active_run_id', currentRunId);
    }
  }, [currentRunId]);

  useEffect(() => {
    if (currentRunState) {
      try {
        localStorage.setItem('helm_active_run_state', JSON.stringify(currentRunState));
      } catch (err) {
        console.warn('Could not save state to localStorage', err);
      }
    }
  }, [currentRunState]);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (res.ok) setHealth(await res.json());
    } catch (err) {
      console.warn('Could not fetch health status', err);
    }
  }, []);

  const fetchRecentRuns = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/runs`);
      if (res.ok) setRecentRuns(await res.json());
    } catch (err) {
      console.warn('Could not fetch recent runs', err);
    }
  }, []);

  const fetchSyntheticData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/synthetic/current`);
      if (res.ok) setSyntheticSnapshot(await res.json());
    } catch (err) {
      console.warn('Could not fetch synthetic snapshot', err);
    }
  }, []);

  const stopLiveStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setLiveMode(null);
  }, []);

  const handleSettled = useCallback(
    (state) => {
      stopLiveStream();
      setIsOrchestrating(false);
      fetchRecentRuns();
      if (state?.status === 'failed') {
        console.warn('Run failed:', state.error);
      }
    },
    [stopLiveStream, fetchRecentRuns]
  );

  // Fallback: classic 1s polling (used only if the SSE stream errors out).
  const startPollingFallback = useCallback(
    (runId) => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      setLiveMode('poll');
      pollTimerRef.current = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/runs/${runId}`);
          if (!res.ok) return;
          const state = await res.json();
          setCurrentRunState(state);
          if (SETTLED.includes(state.status)) handleSettled(state);
        } catch (err) {
          console.warn('Polling error:', err);
        }
      }, 1000);
    },
    [handleSettled]
  );

  // Primary: Server-Sent Events — the backend pushes every hop checkpoint
  // the moment it lands (~250ms latency), no request spam.
  const subscribeToRun = useCallback(
    (runId) => {
      stopLiveStream();
      setIsOrchestrating(true);

      let gotFirstEvent = false;
      const es = new EventSource(`${API_BASE}/api/runs/${runId}/events`);
      eventSourceRef.current = es;
      setLiveMode('sse');

      es.addEventListener('state', (evt) => {
        gotFirstEvent = true;
        try {
          const state = JSON.parse(evt.data);
          setCurrentRunState(state);
        } catch (err) {
          console.warn('Bad SSE payload', err);
        }
      });

      es.addEventListener('done', () => {
        es.close();
        eventSourceRef.current = null;
        setLiveMode(null);
        // Latest state already delivered via the preceding `state` event.
        setIsOrchestrating(false);
        fetchRecentRuns();
      });

      es.addEventListener('timeout', () => {
        es.close();
        eventSourceRef.current = null;
        startPollingFallback(runId);
      });

      es.onerror = () => {
        // EventSource retries on transient errors by itself; only fall back
        // to polling if the stream dies before delivering anything.
        if (!gotFirstEvent && es.readyState === EventSource.CLOSED) {
          eventSourceRef.current = null;
          startPollingFallback(runId);
        }
      };
    },
    [stopLiveStream, startPollingFallback, fetchRecentRuns]
  );

  // Load an existing run; if it's still running, seamlessly re-attach the
  // live stream (page refresh mid-run keeps streaming).
  const loadRun = useCallback(
    async (runId) => {
      try {
        const res = await fetch(`${API_BASE}/api/runs/${runId}`);
        if (!res.ok) return;
        const data = await res.json();
        setCurrentRunId(data.run_id);
        setCurrentRunState(data);
        if (data.status === 'running') {
          subscribeToRun(data.run_id);
        } else {
          setIsOrchestrating(false);
        }
      } catch (err) {
        console.warn(`Could not load run ${runId}`, err);
      }
    },
    [subscribeToRun]
  );

  // Start new Governor mission and attach the live stream immediately.
  const startMission = useCallback(
    async (objective) => {
      setIsOrchestrating(true);
      try {
        const res = await fetch(`${API_BASE}/api/runs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ objective }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setCurrentRunId(data.run_id);
        setCurrentRunState({
          run_id: data.run_id,
          objective,
          status: 'running',
          hops: [],
          agent_reports: {},
        });
        subscribeToRun(data.run_id);
      } catch (err) {
        setIsOrchestrating(false);
        alert(`Governor start failed: ${err.message}`);
      }
    },
    [subscribeToRun]
  );

  const resolveApproval = useCallback(
    async (decision, decisionNotes = '') => {
      if (!currentRunId) return;
      try {
        const res = await fetch(`${API_BASE}/api/runs/${currentRunId}/approval`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ decision, decision_notes: decisionNotes }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setCurrentRunState(data);
        fetchRecentRuns();
      } catch (err) {
        alert(`Approval submission failed: ${err.message}`);
      }
    },
    [currentRunId, fetchRecentRuns]
  );

  const generateSyntheticScenario = useCallback(
    async (scenario, days = 60) => {
      try {
        const res = await fetch(`${API_BASE}/api/synthetic/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario, days }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        await fetchSyntheticData();
        await fetchHealth();
      } catch (err) {
        alert(`Synthetic generation failed: ${err.message}`);
      }
    },
    [fetchSyntheticData, fetchHealth]
  );

  // Mount once: telemetry + resume any persisted run (re-attaching its
  // live stream if it is still mid-relay). Cleanup closes the stream.
  useEffect(() => {
    fetchHealth();
    fetchRecentRuns();
    fetchSyntheticData();
    const savedRunId = localStorage.getItem('helm_active_run_id');
    if (savedRunId) loadRun(savedRunId);
    return stopLiveStream;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <HelmStoreContext.Provider
      value={{
        activeTab,
        setActiveTab,
        currentRunId,
        currentRunState,
        health,
        recentRuns,
        syntheticSnapshot,
        isOrchestrating,
        liveMode,
        startMission,
        loadRun,
        resolveApproval,
        generateSyntheticScenario,
        fetchSyntheticData,
      }}
    >
      {children}
    </HelmStoreContext.Provider>
  );
}

export function useHelmStore() {
  const context = useContext(HelmStoreContext);
  if (!context) {
    throw new Error('useHelmStore must be used within HelmStoreProvider');
  }
  return context;
}
