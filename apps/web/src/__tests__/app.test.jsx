/**
 * Render smoke tests.
 *
 * These stand in for a manual click-through: they mount the real shell against
 * a stubbed API and assert that every screen and every agent block type
 * actually renders. A crash in any component — a bad field name, a missing
 * guard on empty data — fails here rather than in front of an operator.
 */

import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from '../App';
import { HelmProvider } from '../store';
import { BlockRenderer } from '../components/blocks/BlockRenderer';
import { TrendChart, ChannelBars, Sparkline, ScoreBar } from '../components/Charts';

const HEALTH = {
  status: 'healthy',
  active_provider: 'anthropic',
  active_model: 'claude-opus-5',
  gateway_mode: 'live',
  data_source: 'synthetic',
  dry_run: true,
  connections: { google_ads: false, meta_ads: false },
};

const SERIES = Array.from({ length: 30 }, (_, i) => ({
  date: `2026-07-${String(i + 1).padStart(2, '0')}`,
  spend: 200000 + i * 4000,
  conversions: 1500 + i * 20,
  roas: 2.4 + (i % 5) * 0.05,
  cpa: 130 - (i % 4),
  clicks: 40000 + i * 300,
}));

const OVERVIEW = {
  data_source: 'synthetic',
  data_source_label: 'Synthetic dataset',
  period_days: 30,
  kpis: [
    { key: 'spend', label: 'Total spend', value: 6886486.97, format: 'currency', delta_pct: 12.5, improved: true },
    { key: 'roas', label: 'Blended ROAS', value: 2.5, format: 'multiple', delta_pct: 2.0, improved: true },
    { key: 'cpa', label: 'Blended CPA', value: 129.3, format: 'currency', delta_pct: 3.7, improved: false },
    { key: 'conversions', label: 'Conversions', value: 53260, format: 'number' },
  ],
  secondary_kpis: [
    { key: 'clicks', label: 'Clicks', value: 1351441, format: 'number' },
    { key: 'impressions', label: 'Impressions', value: 31073577, format: 'number' },
    { key: 'ctr', label: 'Blended CTR', value: 4.35, format: 'percent' },
    { key: 'campaigns', label: 'Active campaigns', value: 5, format: 'number' },
  ],
  timeseries: SERIES,
  channels: [
    { key: 'google_ads', label: 'Google Ads', campaign_count: 2, spend_inr: 2839796, share: 41.2, roas: 3.4, cpa_inr: 106 },
    { key: 'meta_ads', label: 'Meta', campaign_count: 3, spend_inr: 4046690, share: 58.8, roas: 1.87, cpa_inr: 152 },
  ],
  campaigns: [
    {
      campaign_id: 'c1',
      campaign_name: 'Wealth Accelerator Performance Max',
      platform: 'google_ads',
      platform_label: 'Google Ads',
      spend_inr: 1491076,
      roas: 3.4,
      cpa_inr: 106.1,
      ctr: 6.72,
      conversions: 14053,
      score: 84,
      verdict: 'WINNER',
    },
  ],
  alerts: [{ severity: 'critical', title: 'Performance decay', detail: 'Gold ETF CPA rose 285%' }],
  pending_approvals: [{ run_id: 'run_1', objective: 'Reduce CPA', updated_at: '' }],
};

const AGENTS = [
  { id: 'governor', label: 'Governor', role: 'Orchestration', color: 'purple', icon: 'security', description: 'Runs the relay' },
  { id: 'analyst', label: 'Analyst', role: 'Insight', color: 'blue', icon: 'query_stats', description: 'Diagnoses performance' },
  { id: 'creative', label: 'Creative', role: 'Copy', color: 'purple', icon: 'palette', description: 'Writes variations' },
  { id: 'media_buyer', label: 'Media Buyer', role: 'Budget', color: 'orange', icon: 'ads_click', description: 'Reallocates budget' },
  { id: 'compliance', label: 'Compliance', role: 'SEBI', color: 'green', icon: 'verified_user', description: 'Scans copy' },
];

/** Route each stubbed endpoint by URL, the way the real server would. */
function stubApi(overrides = {}) {
  const routes = {
    '/api/health': HEALTH,
    '/api/dashboard/overview': OVERVIEW,
    '/api/agents': AGENTS,
    '/api/reports': [],
    '/api/runs': [],
    '/api/synthetic/scenarios': [],
    '/api/synthetic/current': {
      source: 'synthetic',
      campaign_count: 0,
      total_spend_inr: 0,
      blended_roas: 0,
      campaigns: [],
    },
    '/api/connections': { google_ads: { connected: false }, meta_ads: { connected: false } },
    ...overrides,
  };

  global.fetch = vi.fn(async (url) => {
    const path = String(url).split('?')[0];
    const body = routes[path];
    return {
      ok: body !== undefined,
      status: body !== undefined ? 200 : 404,
      headers: { get: () => 'application/json' },
      json: async () => (body !== undefined ? body : { detail: `No stub for ${path}` }),
    };
  });
}

function renderApp() {
  return render(
    <HelmProvider>
      <App />
    </HelmProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

// Vitest runs with `globals: false`, so Testing Library's automatic cleanup
// never registers itself — unmount explicitly or DOM leaks across tests.
afterEach(cleanup);

describe('command center', () => {
  it('renders headline KPIs with Indian digit grouping', async () => {
    stubApi();
    renderApp();

    // Appears twice: the nav rail item and the page title.
    expect((await screen.findAllByText('Command Center')).length).toBe(2);
    expect(await screen.findByText('₹68,86,487')).toBeTruthy();
    expect(screen.getByText('2.5x')).toBeTruthy();
  });

  it('shows period-over-period deltas', async () => {
    stubApi();
    renderApp();
    expect(await screen.findByText(/\+12\.5%/)).toBeTruthy();
  });

  it('surfaces pending approvals above the fold', async () => {
    stubApi();
    renderApp();
    expect(await screen.findByText(/1 proposal awaiting your approval/)).toBeTruthy();
  });

  it('renders the campaign table and channel split', async () => {
    stubApi();
    renderApp();
    expect(await screen.findByText('Wealth Accelerator Performance Max')).toBeTruthy();
    expect(screen.getByText('WINNER')).toBeTruthy();
    expect(screen.getAllByText('Google Ads').length).toBeGreaterThan(0);
  });

  it('reports an unreachable API instead of rendering fake numbers', async () => {
    global.fetch = vi.fn(async () => {
      throw new Error('network down');
    });
    renderApp();
    expect(await screen.findByText('Could not load account data')).toBeTruthy();
    expect(screen.queryByText(/₹68,86,487/)).toBeNull();
  });

  it('never offers a model picker — HELM runs on Claude', async () => {
    stubApi();
    renderApp();
    await screen.findAllByText('Command Center');
    expect(screen.queryByText(/gemini/i)).toBeNull();
    expect(screen.queryByText(/switch model/i)).toBeNull();
    // The active model is reported, not chosen.
    expect(screen.getByText('claude-opus-5')).toBeTruthy();
  });
});

describe('screen navigation', () => {
  const cases = [
    ['agents', 'Agents'],
    ['pipeline', 'Pipeline'],
    ['reports', 'Reports'],
    ['data', 'Data Sources'],
    ['audit', 'Audit Trail'],
    ['settings', 'Settings'],
  ];

  it.each(cases)('renders the %s screen', async (screenId, heading) => {
    localStorage.setItem('helm.prefs.v2', JSON.stringify({ screen: screenId }));
    stubApi();
    renderApp();
    expect((await screen.findAllByText(heading)).length).toBeGreaterThan(0);
  });

  it('gives every agent its own console entry', async () => {
    localStorage.setItem('helm.prefs.v2', JSON.stringify({ screen: 'agents' }));
    stubApi();
    renderApp();
    for (const agent of AGENTS) {
      expect((await screen.findAllByText(agent.label)).length).toBeGreaterThan(0);
    }
    // The selected agent exposes one-click tasks, not just a text box.
    expect(await screen.findByText(/Which campaigns should I cut/)).toBeTruthy();
    // Attachment button exists with appropriate label
    expect(screen.getByLabelText(/Attach dataset/i)).toBeTruthy();
  });

  it('renders dataset attachment button on Pipeline screen', async () => {
    localStorage.setItem('helm.prefs.v2', JSON.stringify({ screen: 'pipeline' }));
    stubApi();
    renderApp();
    expect(await screen.findByText('Run the pipeline')).toBeTruthy();
    expect(screen.getByText(/Attach dataset/i)).toBeTruthy();
  });

  it('handles file selection, attachment chip rendering, and removal on Agents screen', async () => {
    localStorage.setItem('helm.prefs.v2', JSON.stringify({ screen: 'agents' }));
    stubApi();
    renderApp();
    await screen.findByText(/Which campaigns should I cut/);

    const fileInput = screen.getByLabelText(/Upload dataset/i);
    const file = new File(['campaign_id,campaign_name\n1,Test'], 'test_campaigns.csv', {
      type: 'text/csv',
    });

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText('test_campaigns.csv')).toBeTruthy();
    });
    expect(screen.getByTitle('Remove attachment')).toBeTruthy();

    fireEvent.click(screen.getByTitle('Remove attachment'));
    expect(screen.queryByText('test_campaigns.csv')).toBeNull();
  });

  it('accepts and attaches .pdf files on Agents screen', async () => {
    localStorage.setItem('helm.prefs.v2', JSON.stringify({ screen: 'agents' }));
    stubApi();
    renderApp();
    await screen.findByText(/Which campaigns should I cut/);

    const fileInput = screen.getByLabelText(/Upload dataset/i);
    const pdfFile = new File(['%PDF-1.4 mock pdf text content'], 'marketing_brief.pdf', {
      type: 'application/pdf',
    });

    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    await waitFor(() => {
      expect(screen.getByText('marketing_brief.pdf')).toBeTruthy();
    });
    expect(screen.getByTitle('Remove attachment')).toBeTruthy();
  });

  it('handles drag and drop file upload on Agents screen', async () => {
    localStorage.setItem('helm.prefs.v2', JSON.stringify({ screen: 'agents' }));
    stubApi();
    renderApp();
    await screen.findByText(/Which campaigns should I cut/);

    const form = screen.getByLabelText(/Ask Analyst/i).closest('form');
    expect(form).toBeTruthy();

    const file = new File(['mock excel content'], 'q3_metrics.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    fireEvent.dragOver(form);
    fireEvent.drop(form, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => {
      expect(screen.getByText('q3_metrics.xlsx')).toBeTruthy();
    });
  });

  it('alerts and rejects unsupported file formats on Agents screen', async () => {
    const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {});
    localStorage.setItem('helm.prefs.v2', JSON.stringify({ screen: 'agents' }));
    stubApi();
    renderApp();
    await screen.findByText(/Which campaigns should I cut/);

    const fileInput = screen.getByLabelText(/Upload dataset/i);
    const badFile = new File(['bad content'], 'video.mp4', { type: 'video/mp4' });

    fireEvent.change(fileInput, { target: { files: [badFile] } });

    expect(alertMock).toHaveBeenCalledWith('Please upload a .csv, .xlsx, .xls, .json, or .pdf dataset.');
    expect(screen.queryByText('video.mp4')).toBeNull();
    alertMock.mockRestore();
  });

  it('handles file attachment and removal on Pipeline screen', async () => {
    localStorage.setItem('helm.prefs.v2', JSON.stringify({ screen: 'pipeline' }));
    stubApi();
    renderApp();
    await screen.findByText('Run the pipeline');

    const fileInput = screen.getByLabelText(/Upload dataset for pipeline/i);
    const file = new File(['[{"campaign_id": "c1"}]'], 'pipeline_data.json', {
      type: 'application/json',
    });

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText('pipeline_data.json')).toBeTruthy();
    });
    expect(screen.getByText('Change dataset')).toBeTruthy();

    fireEvent.click(screen.getByTitle('Remove attachment'));
    expect(screen.queryByText('pipeline_data.json')).toBeNull();
  });
});


describe('agent block grammar', () => {
  it('renders every block type the backend emits', () => {
    const blocks = [
      {
        type: 'kpi_grid',
        title: 'Account performance',
        items: [{ label: 'Spend', value: '₹68,86,487', delta: '+12.5%', delta_dir: 'up' }],
      },
      {
        type: 'table',
        title: 'Campaign breakdown',
        columns: [
          { key: 'campaign_name', label: 'Campaign' },
          { key: 'verdict', label: 'Verdict', kind: 'status' },
        ],
        rows: [{ campaign_name: 'Search Intent', verdict: 'WINNER' }],
        footer: { campaign_name: 'Total', verdict: 'PASS' },
      },
      { type: 'bullets', title: 'Watch-outs', tone: 'flag', items: ['CTR fell 35%'] },
      {
        type: 'findings',
        title: 'What the Analyst found',
        items: [
          { title: 'Gold ETF is decaying', detail: 'CPA rose 285% to ₹648', severity: 'critical' },
          { title: 'Google is the engine', detail: '3.4x ROAS', severity: 'opportunity' },
        ],
      },
      {
        type: 'variations',
        title: 'Ad variations',
        items: [
          {
            title: 'Variation 1',
            subtitle: 'Benefit Led',
            headline: 'Start a disciplined SIP',
            body: 'Body copy',
            cta: 'Learn more',
            note: 'Leads with control',
            status: 'PASS',
            violations: [],
          },
        ],
      },
      {
        type: 'policy_check',
        title: 'Policy check',
        verdict: 'PASS',
        counts: { PASS: 2, FLAG: 1, BLOCK: 0 },
        items: [{ label: 'Within ±25% limit', status: 'PASS' }],
      },
      {
        type: 'rewrite',
        title: 'Compliant rewrite',
        original: 'Guaranteed returns',
        revised: 'Historically strong returns. Subject to market risks.',
      },
      { type: 'stepper', title: 'Progress', steps: [{ label: 'Analyst', status: 'completed' }] },
      { type: 'text', title: 'Brief', fields: [{ label: 'Audience', value: 'Salaried professionals' }] },
      { type: 'something_new', payload: { future: true } },
    ];

    render(<BlockRenderer blocks={blocks} />);

    expect(screen.getByText('Account performance')).toBeTruthy();
    expect(screen.getByText('Search Intent')).toBeTruthy();
    expect(screen.getByText('CTR fell 35%')).toBeTruthy();
    expect(screen.getByText('Gold ETF is decaying')).toBeTruthy();
    expect(screen.getByText('critical')).toBeTruthy();
    expect(screen.getByText('Start a disciplined SIP')).toBeTruthy();
    expect(screen.getByText('Leads with control')).toBeTruthy();
    expect(screen.getByText('Within ±25% limit')).toBeTruthy();
    expect(screen.getByText('Guaranteed returns')).toBeTruthy();
    expect(screen.getByText(/Historically strong returns/)).toBeTruthy();
    expect(screen.getByText('Salaried professionals')).toBeTruthy();
    // Unknown types degrade to an inspectable dump rather than crashing.
    expect(screen.getByText(/Raw block: something_new/)).toBeTruthy();
  });

  it('renders nothing for an empty block list', () => {
    const { container } = render(<BlockRenderer blocks={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('skips a table with no rows rather than rendering an empty shell', () => {
    const { container } = render(
      <BlockRenderer
        blocks={[{ type: 'table', title: 'Empty', columns: [{ key: 'a', label: 'A' }], rows: [] }]}
      />,
    );
    expect(within(container).queryByText('Empty')).toBeNull();
  });
});

describe('charts', () => {
  it('plots a trend series', () => {
    const { container } = render(<TrendChart data={SERIES} metric="spend" label="Spend" format="currency" />);
    expect(container.querySelector('svg')).toBeTruthy();
    expect(container.querySelectorAll('path').length).toBeGreaterThanOrEqual(2);
  });

  it('explains itself rather than drawing a misleading line from one point', () => {
    render(<TrendChart data={[{ date: '2026-07-01', spend: 1 }]} metric="spend" />);
    expect(screen.getByText(/Not enough data points/)).toBeTruthy();
  });

  it('directly labels every channel bar, so color is never the only signal', () => {
    render(<ChannelBars channels={OVERVIEW.channels} />);
    expect(screen.getByText('Google Ads')).toBeTruthy();
    expect(screen.getByText('Meta')).toBeTruthy();
    expect(screen.getByText(/41\.2%/)).toBeTruthy();
  });

  it('renders a sparkline only when there is a trend to show', () => {
    const { container: empty } = render(<Sparkline data={[{ spend: 1 }]} />);
    expect(empty.querySelector('svg')).toBeNull();
    cleanup();
    const { container: full } = render(<Sparkline data={SERIES} />);
    expect(full.querySelector('path')).toBeTruthy();
  });

  it('shows the numeric score beside the score bar', () => {
    render(<ScoreBar score={84} />);
    expect(screen.getByText('84')).toBeTruthy();
  });
});
