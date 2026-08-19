/** App shell: fixed navigation rail + a scrolling workspace per screen. */

import React from 'react';
import { useHelm } from './store';
import { Sidebar } from './components/Shell';
import { Icon } from './components/ui';
import { OverviewScreen } from './screens/OverviewScreen';
import { AgentsScreen } from './screens/AgentsScreen';
import { PipelineScreen } from './screens/PipelineScreen';
import { ReportsScreen } from './screens/ReportsScreen';
import { DataSourcesScreen } from './screens/DataSourcesScreen';
import { AuditScreen } from './screens/AuditScreen';
import { SettingsScreen } from './screens/SettingsScreen';

const SCREENS = {
  overview: OverviewScreen,
  agents: AgentsScreen,
  pipeline: PipelineScreen,
  reports: ReportsScreen,
  data: DataSourcesScreen,
  audit: AuditScreen,
  settings: SettingsScreen,
};

export default function App() {
  const { screen, toast } = useHelm();
  const Screen = SCREENS[screen] || OverviewScreen;

  return (
    <div className="h-full">
      <Sidebar />
      <main className="h-full lg:pl-[248px] overflow-y-auto bg-surface">
        <Screen />
      </main>
      {toast && <Toast toast={toast} />}
    </div>
  );
}

function Toast({ toast }) {
  const tones = {
    success: 'bg-green-700 text-white',
    warn: 'bg-amber-600 text-white',
    error: 'bg-error text-on-error',
  };
  return (
    <div
      role="status"
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-lg animate-fade-up max-w-md ${
        tones[toast.tone] || tones.success
      }`}
    >
      <Icon
        name={toast.tone === 'success' ? 'check_circle' : 'info'}
        size={20}
        fill
        className="shrink-0"
      />
      <span className="text-body-sm font-medium">{toast.text}</span>
    </div>
  );
}
