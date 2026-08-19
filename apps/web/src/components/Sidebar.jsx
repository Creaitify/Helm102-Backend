import React from 'react';
import { useHelmStore } from '../context/HelmStore';

export function Sidebar({ onOpenDataCenter }) {
  const { activeTab, setActiveTab, clearActiveRun, currentRunState } = useHelmStore();
  const isPending = currentRunState?.status === 'pending_approval';

  const navItems = [
    { id: 'analysis', label: 'Campaign Performance', icon: 'analytics', time: '2m ago' },
    { id: 'creative', label: 'Ad Creative - Review', icon: 'brush', time: '1h ago' },
    { id: 'budget', label: 'Budget Optimization', icon: 'account_balance_wallet', time: 'Yesterday' },
    { id: 'approval', label: 'Approval Required', icon: 'pending_actions', time: isPending ? 'Action Required' : 'New', urgent: isPending },
    { id: 'overview', label: 'Q3 Executive Summary', icon: 'summarize', time: '2d ago' },
    { id: 'datacenter', label: 'Data Ingestion Center', icon: 'database', time: 'BYOD', isAction: true },
    { id: 'audit', label: 'Immutable Audit Trail', icon: 'receipt_long', time: 'Audit' },
  ];

  const handleNewConversation = () => {
    clearActiveRun();
    setActiveTab('overview');
  };

  return (
    <aside className="fixed left-0 top-0 h-full w-[280px] flex flex-col z-50 bg-inverse-surface text-on-primary-container border-r border-outline-variant/10 shadow-lg select-none">
      {/* Brand Header */}
      <div className="p-6 border-b border-outline-variant/10 flex items-center gap-3">
        <button
          onClick={() => setActiveTab('overview')}
          className="flex items-center gap-3 text-left focus:outline-none"
        >
          <span className="material-symbols-outlined icon-fill text-primary-fixed-dim text-2xl">sailing</span>
          <span className="text-headline-xl font-headline-xl font-black text-on-primary-container tracking-tighter">
            HELM
          </span>
        </button>
      </div>

      {/* New Conversation Button */}
      <div className="p-4">
        <button
          onClick={handleNewConversation}
          className="w-full bg-primary hover:bg-on-primary-fixed-variant text-on-primary font-headline-md text-sm py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-all shadow-sm border border-outline-variant/20 active:scale-[0.98]"
        >
          <span className="material-symbols-outlined text-[20px]">add</span>
          New Conversation
        </button>
      </div>

      {/* Navigation List */}
      <div className="flex-1 overflow-y-auto py-2">
        <div className="px-4 mb-2">
          <span className="font-label-mono text-[10px] text-outline-variant uppercase tracking-wider">
            Recent Conversations
          </span>
        </div>
        <nav className="space-y-1 mb-6">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (item.id === 'datacenter' && onOpenDataCenter) {
                    onOpenDataCenter();
                  } else {
                    setActiveTab(item.id);
                  }
                }}
                className={`w-full text-left flex items-center gap-3 px-4 py-3 transition-colors ${
                  isActive
                    ? 'bg-secondary-fixed-dim/20 text-on-primary-container border-l-4 border-primary-fixed-dim'
                    : 'text-outline-variant hover:text-on-primary-container hover:bg-secondary-fixed-dim/10 border-l-4 border-transparent'
                }`}
              >
                <span
                  className={`material-symbols-outlined text-[20px] ${
                    isActive ? 'text-primary-fixed-dim' : ''
                  }`}
                >
                  {item.icon}
                </span>
                <span className="font-label-mono text-[12px] truncate flex-1">{item.label}</span>
                <span
                  className={`text-[10px] whitespace-nowrap ${
                    item.urgent ? 'text-agent-orange font-bold animate-pulse' : 'text-outline-variant'
                  }`}
                >
                  {item.time}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="px-4 mb-2 mt-4 pt-4 border-t border-outline-variant/10">
          <span className="font-label-mono text-[10px] text-outline-variant uppercase tracking-wider">
            Resources
          </span>
        </div>
        <nav className="space-y-1">
          {[
            { label: 'Prompt Library', icon: 'menu_book' },
            { label: 'Documents', icon: 'description' },
            { label: 'Reports', icon: 'bar_chart' },
            { label: 'Settings', icon: 'settings' },
          ].map((resource) => (
            <button
              key={resource.label}
              onClick={() => alert(`${resource.label} is available in enterprise control plane.`)}
              className="w-full text-left flex items-center gap-3 px-4 py-3 text-outline-variant hover:text-on-primary-container hover:bg-secondary-fixed-dim/10 transition-colors"
            >
              <span className="material-symbols-outlined text-[20px]">{resource.icon}</span>
              <span className="font-label-mono text-[12px]">{resource.label}</span>
            </button>
          ))}
        </nav>
      </div>
    </aside>
  );
}
