import React from 'react';
import { useHelmStore } from '../context/HelmStore';
import {
  Layers,
  BarChart3,
  Sparkles,
  ShieldCheck,
  DollarSign,
  CheckSquare,
  FileText,
} from 'lucide-react';

const TABS = [
  { id: 'governor', num: '01', title: 'Governor HQ', icon: Layers },
  { id: 'adops', num: '02', title: 'Ad-Ops Workspace', icon: BarChart3 },
  { id: 'creative', num: '03', title: 'Creative Studio', icon: Sparkles },
  { id: 'compliance', num: '04', title: 'Compliance Shield', icon: ShieldCheck },
  { id: 'budget', num: '05', title: 'Budget Optimizer', icon: DollarSign },
  { id: 'execution', num: '06', title: 'Execution Engine', icon: CheckSquare },
  { id: 'audit', num: '07', title: 'Audit Trail', icon: FileText },
];

export function Navigation() {
  const { activeTab, setActiveTab, currentRunState } = useHelmStore();
  const isPending = currentRunState?.status === 'pending_approval';

  return (
    <nav className="nav-tabs" role="tablist">
      {TABS.map(({ id, num, title, icon: Icon }) => (
        <button
          key={id}
          className={`nav-tab ${activeTab === id ? 'active' : ''}`}
          onClick={() => setActiveTab(id)}
          role="tab"
        >
          <span className="tab-num">{num}</span>
          <Icon style={{ width: 16, height: 16 }} />
          <span className="tab-title">{title}</span>
          {id === 'execution' && isPending && (
            <span className="badge-count">1</span>
          )}
        </button>
      ))}
    </nav>
  );
}
