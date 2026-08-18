import React from 'react';
import { useHelmStore } from './context/HelmStore';
import { Header } from './components/Header';
import { Navigation } from './components/Navigation';
import { GovernorWorkspace } from './components/workspaces/GovernorWorkspace';
import { AdOpsWorkspace } from './components/workspaces/AdOpsWorkspace';
import { CreativeWorkspace } from './components/workspaces/CreativeWorkspace';
import { ComplianceWorkspace } from './components/workspaces/ComplianceWorkspace';
import { BudgetWorkspace } from './components/workspaces/BudgetWorkspace';
import { ExecutionWorkspace } from './components/workspaces/ExecutionWorkspace';
import { AuditWorkspace } from './components/workspaces/AuditWorkspace';

export default function App() {
  const { activeTab } = useHelmStore();

  return (
    <div className="app-shell">
      <Header />
      <Navigation />

      <main className="main-content">
        {activeTab === 'governor' && <GovernorWorkspace />}
        {activeTab === 'adops' && <AdOpsWorkspace />}
        {activeTab === 'creative' && <CreativeWorkspace />}
        {activeTab === 'compliance' && <ComplianceWorkspace />}
        {activeTab === 'budget' && <BudgetWorkspace />}
        {activeTab === 'execution' && <ExecutionWorkspace />}
        {activeTab === 'audit' && <AuditWorkspace />}
      </main>
    </div>
  );
}
