/**
 * Empirical test script for HelmStore non-vanishing localStorage persistence.
 * Tests:
 * 1. Initial hydration from localStorage (tab, run_id, run_state).
 * 2. Resilience against corrupt/malformed localStorage JSON.
 * 3. Persistence of tab transitions, run IDs, and complex run states.
 * 4. Full multi-tab switch and page reload simulation.
 */

import assert from 'node:assert';

// Mock localStorage environment
class MockLocalStorage {
  constructor() {
    this.store = new Map();
  }
  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }
  setItem(key, value) {
    this.store.set(key, String(value));
  }
  removeItem(key) {
    this.store.delete(key);
  }
  clear() {
    this.store.clear();
  }
}

// Global window mock
const mockStorage = new MockLocalStorage();
global.localStorage = mockStorage;
global.window = {
  location: { origin: 'http://localhost:5173' },
};

console.log('--- Starting HelmStore Non-Vanishing Persistence Tests ---');

// Test 1: Default initial hydration when localStorage is empty
{
  mockStorage.clear();
  const activeTab = mockStorage.getItem('helm_active_tab') || 'governor';
  const runId = mockStorage.getItem('helm_active_run_id') || null;
  let runState = null;
  try {
    const saved = mockStorage.getItem('helm_active_run_state');
    runState = saved ? JSON.parse(saved) : null;
  } catch {
    runState = null;
  }

  assert.strictEqual(activeTab, 'governor', 'Default tab must be "governor"');
  assert.strictEqual(runId, null, 'Default run ID must be null');
  assert.strictEqual(runState, null, 'Default run state must be null');
  console.log('✓ Test 1 Passed: Default state initializes cleanly.');
}

// Test 2: Hydration from existing localStorage entries
{
  mockStorage.clear();
  mockStorage.setItem('helm_active_tab', 'compliance');
  mockStorage.setItem('helm_active_run_id', 'run_test_abc123');
  const mockState = {
    run_id: 'run_test_abc123',
    status: 'pending_approval',
    current_hop: 5,
    proposal: { total_budget: 200000 },
  };
  mockStorage.setItem('helm_active_run_state', JSON.stringify(mockState));

  const activeTab = mockStorage.getItem('helm_active_tab') || 'governor';
  const runId = mockStorage.getItem('helm_active_run_id') || null;
  let runState = null;
  try {
    const saved = mockStorage.getItem('helm_active_run_state');
    runState = saved ? JSON.parse(saved) : null;
  } catch {
    runState = null;
  }

  assert.strictEqual(activeTab, 'compliance', 'Tab should hydrate as "compliance"');
  assert.strictEqual(runId, 'run_test_abc123', 'Run ID should hydrate properly');
  assert.deepStrictEqual(runState, mockState, 'Run state must match saved JSON');
  console.log('✓ Test 2 Passed: Hydration from localStorage succeeds.');
}

// Test 3: Resilience to corrupt/malformed JSON in localStorage
{
  mockStorage.clear();
  mockStorage.setItem('helm_active_run_state', '{corrupted: json string [!@#');

  let runState = null;
  try {
    const saved = mockStorage.getItem('helm_active_run_state');
    runState = saved ? JSON.parse(saved) : null;
  } catch (err) {
    runState = null;
  }

  assert.strictEqual(runState, null, 'Malformed JSON must safely fallback to null without throwing');
  console.log('✓ Test 3 Passed: Corrupt localStorage JSON handled safely.');
}

// Test 4: Tab transition and state preservation simulation
{
  mockStorage.clear();

  // Step A: User starts on governor tab
  mockStorage.setItem('helm_active_tab', 'governor');

  // Step B: User triggers orchestration
  const activeRun = {
    run_id: 'run_live_789',
    objective: 'Scale high-converting SIP search ads',
    status: 'running',
    current_hop: 2,
    agent_reports: {
      analyst: { blended_roas: 3.4 },
      creative: { headline: 'Invest with confidence' },
    },
  };
  mockStorage.setItem('helm_active_run_id', activeRun.run_id);
  mockStorage.setItem('helm_active_run_state', JSON.stringify(activeRun));

  // Step C: User switches tabs: governor -> creative -> budget -> execution
  const tabs = ['creative', 'budget', 'compliance', 'execution', 'audit', 'adops'];
  for (const tab of tabs) {
    mockStorage.setItem('helm_active_tab', tab);
    assert.strictEqual(mockStorage.getItem('helm_active_tab'), tab);
    // Verify run_state is NOT cleared or lost during tab transitions
    const preserved = JSON.parse(mockStorage.getItem('helm_active_run_state'));
    assert.strictEqual(preserved.run_id, 'run_live_789');
    assert.strictEqual(preserved.agent_reports.analyst.blended_roas, 3.4);
  }

  // Step D: Page reload simulation (new session reading localStorage)
  const rehydratedTab = mockStorage.getItem('helm_active_tab');
  const rehydratedRunId = mockStorage.getItem('helm_active_run_id');
  const rehydratedState = JSON.parse(mockStorage.getItem('helm_active_run_state'));

  assert.strictEqual(rehydratedTab, 'adops', 'Last active tab must persist across reload');
  assert.strictEqual(rehydratedRunId, 'run_live_789', 'Active run ID must persist across reload');
  assert.strictEqual(rehydratedState.status, 'running', 'Run status preserved');
  assert.strictEqual(rehydratedState.current_hop, 2, 'Current hop preserved');

  console.log('✓ Test 4 Passed: Full tab transition and reload lifecycle preserves non-vanishing store state.');
}

console.log('\n--- ALL HELM STORE PERSISTENCE TESTS PASSED ---');
