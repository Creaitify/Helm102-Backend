import React from 'react';
import { useHelmStore } from '../context/HelmStore';

export function RightSidebar({ onOpenDataCenter }) {
  const {
    activeTab,
    setActiveTab,
    currentRunState,
    syntheticSnapshot,
    byodSnapshot,
    resolveApproval,
  } = useHelmStore();

  const status = currentRunState?.status || 'idle';
  const hops = currentRunState?.hops || [];
  const analystDone = hops.some((h) => h.hop_index === 1 && h.status === 'success');
  const creativeDone = hops.some((h) => h.hop_index === 2 && h.status === 'success');
  const budgetDone = hops.some((h) => h.hop_index === 4 && h.status === 'success');
  const isPending = status === 'pending_approval';

  const agents = [
    {
      id: 'Governor',
      icon: 'security',
      color: 'text-secondary',
      status: status === 'running' ? 'Active' : status === 'completed' ? 'Completed' : 'Idle',
    },
    {
      id: 'Analyst',
      icon: 'query_stats',
      color: 'text-blue-600',
      status: analystDone ? 'Completed' : status === 'running' ? 'Analyzing' : 'Idle',
    },
    {
      id: 'Creative',
      icon: 'palette',
      color: 'text-purple-600',
      status: creativeDone ? 'Completed' : status === 'running' ? 'Drafting' : 'Idle',
    },
    {
      id: 'Media Buyer',
      icon: 'ads_click',
      color: 'text-orange-600',
      status: isPending ? 'Waiting' : budgetDone ? 'Completed' : status === 'running' ? 'Optimizing' : 'Idle',
    },
  ];

  const campaignsCount =
    byodSnapshot?.campaigns?.length ||
    syntheticSnapshot?.campaigns?.length ||
    12;

  const totalSpend =
    byodSnapshot?.total_spend_inr ||
    syntheticSnapshot?.total_spend_inr ||
    1245000;

  return (
    <aside className="fixed right-0 top-0 h-full w-[280px] flex flex-col z-40 bg-surface-container-low text-secondary border-l border-outline-variant/30 select-none">
      {/* Header */}
      <div className="p-6 border-b border-outline-variant/20 flex flex-col gap-1">
        <span className="text-headline-md font-headline-md text-on-surface-variant">Agent Status</span>
        <span className="text-xs text-outline">System Oversight</span>
      </div>

      {/* Agents List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <div className="space-y-2">
          {agents.map((agent) => {
            const isActive =
              (activeTab === 'analysis' && agent.id === 'Analyst') ||
              (activeTab === 'creative' && agent.id === 'Creative') ||
              (activeTab === 'budget' && agent.id === 'Media Buyer') ||
              (activeTab === 'approval' && agent.id === 'Media Buyer') ||
              (activeTab === 'overview' && agent.id === 'Governor');

            return (
              <div
                key={agent.id}
                className={`flex items-center justify-between p-widget-gap rounded-lg border transition-colors ${
                  isActive
                    ? 'bg-surface border-primary/40 shadow-sm'
                    : 'bg-surface-container-lowest border-outline-variant/20'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-8 h-8 rounded bg-surface-container flex items-center justify-center ${
                      isActive ? agent.color : 'text-outline'
                    }`}
                  >
                    <span className="material-symbols-outlined text-[18px]">{agent.icon}</span>
                  </div>
                  <span className="font-label-mono text-[12px] font-medium">{agent.id}</span>
                </div>
                <span
                  className={`text-[10px] font-bold uppercase ${
                    agent.status === 'Completed'
                      ? 'text-green-600'
                      : agent.status === 'Waiting' || agent.status === 'Active' || agent.status === 'Analyzing'
                      ? 'text-orange-500'
                      : 'text-outline'
                  }`}
                >
                  {agent.status}
                </span>
              </div>
            );
          })}
        </div>

        <hr className="border-outline-variant/20" />

        {/* Contextual Sub-panels */}
        {activeTab === 'analysis' && (
          <div>
            <h3 className="font-label-mono text-[10px] text-outline mb-3 uppercase tracking-wider font-bold">
              Sources Used
            </h3>
            <div className="bg-surface-container-lowest rounded-lg border border-outline-variant/20 shadow-sm overflow-hidden">
              {[
                { title: 'Campaign Performance Report', lines: 'Lines 42-48' },
                { title: 'Meta Ads Report', lines: 'Lines 12-28' },
                { title: 'Google Search Report', lines: 'Lines 05-30' },
              ].map((doc, i) => (
                <div
                  key={i}
                  className="p-3 border-b border-outline-variant/10 hover:bg-surface-container-low/50 cursor-pointer flex gap-3"
                >
                  <span className="material-symbols-outlined text-outline text-[16px] mt-0.5">
                    description
                  </span>
                  <div>
                    <div className="text-[12px] text-on-surface font-medium line-clamp-1">
                      {doc.title}
                    </div>
                    <div className="font-label-mono text-[10px] text-outline mt-1">{doc.lines}</div>
                  </div>
                </div>
              ))}
              <div className="p-2 text-center border-t border-outline-variant/10 bg-surface-container-low/30">
                <button
                  onClick={onOpenDataCenter}
                  className="font-label-mono text-[11px] text-primary hover:underline"
                >
                  Manage Data Center (BYOD)
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'creative' && (
          <div>
            <h4 className="text-[12px] font-headline-md text-on-surface-variant mb-3">Compliance Summary</h4>
            <div className="bg-surface rounded-xl border border-outline-variant/30 p-4 shadow-sm">
              <div className="flex justify-between items-end">
                <div className="text-center flex-1 border-r border-outline-variant/20">
                  <div className="text-[10px] font-label-mono text-[#137333] mb-1 font-bold">PASS</div>
                  <div className="text-lg font-black text-on-surface">2</div>
                </div>
                <div className="text-center flex-1 border-r border-outline-variant/20">
                  <div className="text-[10px] font-label-mono text-[#E37400] mb-1 font-bold">FLAG</div>
                  <div className="text-lg font-black text-on-surface">1</div>
                </div>
                <div className="text-center flex-1">
                  <div className="text-[10px] font-label-mono text-[#C5221F] mb-1 font-bold">BLOCK</div>
                  <div className="text-lg font-black text-on-surface">0</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'budget' && (
          <div className="bg-surface border border-outline-variant/30 rounded-xl p-4 space-y-4 shadow-sm">
            <h4 className="font-headline-md text-xs text-on-surface uppercase border-b border-outline-variant/20 pb-2">
              Policy Check
            </h4>
            <div className="space-y-3">
              {['Within ±25% Limit', 'Total Budget Change', 'Reallocation'].map((rule) => (
                <div key={rule} className="flex items-center justify-between text-[11px]">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-success text-[16px]">check_circle</span>
                    <span>{rule}</span>
                  </div>
                  <span className="text-success font-bold">PASS</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'approval' && (
          <div className="space-y-3">
            <h3 className="font-label-mono text-[10px] uppercase text-outline-variant">Approval Actions</h3>
            <button
              onClick={() => resolveApproval('approved', 'Approved by Marketing Lead via Right Panel')}
              className="w-full bg-[#10b981] hover:bg-[#059669] text-white py-2 px-4 rounded-lg text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-all active:scale-95"
            >
              <span className="material-symbols-outlined text-[18px]">check_circle</span> Approve
            </button>
            <button
              onClick={() => resolveApproval('rejected', 'Declined by Marketing Lead')}
              className="w-full bg-[#ef4444] hover:bg-[#dc2626] text-white py-2 px-4 rounded-lg text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-all active:scale-95"
            >
              <span className="material-symbols-outlined text-[18px]">cancel</span> Reject
            </button>
            <button
              onClick={() => setActiveTab('creative')}
              className="w-full bg-surface hover:bg-surface-container border border-outline-variant/50 text-on-surface py-2 px-4 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all active:scale-95"
            >
              <span className="material-symbols-outlined text-[18px]">edit_note</span> Request Changes
            </button>
          </div>
        )}

        {/* Quick Stats (Always available) */}
        <div>
          <h4 className="font-label-mono text-[10px] text-outline mb-3 uppercase tracking-wider">Quick Stats</h4>
          <div className="space-y-3">
            <div className="flex justify-between items-center text-xs">
              <span className="text-on-surface-variant flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] text-outline">campaign</span> Active Campaigns
              </span>
              <span className="font-medium text-on-surface">{campaignsCount}</span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-on-surface-variant flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] text-outline">payments</span> Total Spend (MTD)
              </span>
              <span className="font-medium text-on-surface">₹{Math.round(totalSpend).toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-on-surface-variant flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] text-outline">pending_actions</span> Pending Approvals
              </span>
              <span className="font-medium text-on-surface">{isPending ? 1 : 0}</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
