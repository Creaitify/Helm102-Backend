/** Platform shell: navigation rail + context bar. No chat framing. */

import React from 'react';
import { useHelm } from '../store';
import { Icon } from './ui';

const NAV = [
  { id: 'overview', label: 'Command Center', icon: 'space_dashboard' },
  { id: 'agents', label: 'Agents', icon: 'groups' },
  { id: 'pipeline', label: 'Pipeline', icon: 'account_tree' },
  { id: 'reports', label: 'Reports', icon: 'lab_profile' },
  { id: 'data', label: 'Data Sources', icon: 'database' },
  { id: 'audit', label: 'Audit Trail', icon: 'gavel' },
];

export function Sidebar() {
  const { screen, set, sidebarOpen, overview, health } = useHelm();

  const go = (id) => set({ screen: id, sidebarOpen: false });
  const pending = overview?.pending_approvals?.length || 0;

  return (
    <>
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-inverse-surface/50 z-40 lg:hidden"
          onClick={() => set({ sidebarOpen: false })}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed left-0 top-0 h-full w-[248px] flex flex-col z-50 bg-inverse-surface text-inverse-on-surface transition-transform duration-200 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="px-5 py-5 flex items-center gap-2.5 border-b border-white/10">
          <span className="w-8 h-8 rounded-lg bg-primary text-on-primary grid place-items-center shrink-0">
            <Icon name="sailing" size={19} fill />
          </span>
          <span className="min-w-0">
            <span className="block font-headline text-headline-md font-extrabold tracking-tight leading-none">
              HELM
            </span>
            <span className="block font-mono text-[10px] text-white/45 mt-0.5 truncate">
              Marketing Intelligence
            </span>
          </span>
          <button
            className="ml-auto lg:hidden text-white/60 hover:text-white p-1 rounded focus-ring"
            onClick={() => set({ sidebarOpen: false })}
            aria-label="Close navigation"
          >
            <Icon name="close" size={20} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto scroll-dark p-3" aria-label="Main">
          <ul className="space-y-0.5">
            {NAV.map((item) => {
              const active = screen === item.id;
              return (
                <li key={item.id}>
                  <button
                    onClick={() => go(item.id)}
                    aria-current={active ? 'page' : undefined}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-left focus-ring ${
                      active
                        ? 'bg-primary text-on-primary font-semibold'
                        : 'text-white/65 hover:text-white hover:bg-white/8'
                    }`}
                  >
                    <Icon name={item.icon} size={19} fill={active} />
                    <span className="text-body-sm flex-1">{item.label}</span>
                    {item.id === 'pipeline' && pending > 0 && (
                      <span className="px-1.5 py-0.5 rounded-full bg-viz-warning text-[10px] font-bold text-inverse-surface tabular-nums">
                        {pending}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="p-3 border-t border-white/10">
          <button
            onClick={() => go('settings')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-left focus-ring ${
              screen === 'settings'
                ? 'bg-white/12 text-white font-semibold'
                : 'text-white/65 hover:text-white hover:bg-white/8'
            }`}
          >
            <Icon name="settings" size={19} />
            <span className="text-body-sm">Settings</span>
          </button>

          {health && (
            <div className="mt-3 px-3 py-2.5 rounded-lg bg-white/5">
              <div className="flex items-center gap-1.5 mb-1">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    health.gateway_mode === 'live' ? 'bg-viz-good' : 'bg-viz-warning'
                  }`}
                />
                <span className="font-mono text-[10px] text-white/70 uppercase tracking-wider">
                  {health.gateway_mode === 'live'
                    ? health.active_provider === 'gemini'
                      ? 'Gemini connected'
                      : 'Claude connected'
                    : 'Replay mode'}
                </span>
              </div>
              <p className="font-mono text-[10px] text-white/40 truncate">{health.active_model}</p>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

export function ContextBar({ title, subtitle, actions, breadcrumb }) {
  const { set, overview, health } = useHelm();

  return (
    <header className="sticky top-0 z-30 bg-surface/90 backdrop-blur-md border-b border-outline-variant/40">
      <div className="px-4 sm:px-7 py-3.5 flex items-center gap-4">
        <button
          className="lg:hidden p-2 -ml-2 rounded-lg text-on-surface-variant hover:bg-surface-container-low focus-ring"
          onClick={() => set({ sidebarOpen: true })}
          aria-label="Open navigation"
        >
          <Icon name="menu" size={22} />
        </button>

        <div className="min-w-0 flex-1">
          {breadcrumb && <p className="rail-label mb-0.5">{breadcrumb}</p>}
          <h1 className="font-headline text-headline-lg text-on-surface truncate leading-tight">
            {title}
          </h1>
          {subtitle && (
            <p className="text-body-sm text-on-surface-variant truncate mt-0.5">{subtitle}</p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {overview?.data_source && (
            <span
              className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-surface-container-low border border-outline-variant/40 text-body-sm"
              title={`Campaign data source: ${overview.data_source_label}`}
            >
              <Icon
                name={overview.data_source === 'live' ? 'cloud_done' : 'science'}
                size={15}
                fill
                className={overview.data_source === 'live' ? 'text-viz-good' : 'text-primary'}
              />
              <span className="font-medium">{overview.data_source_label}</span>
            </span>
          )}
          {health && !health.dry_run && (
            <span className="chip bg-error-container text-on-error-container border border-error/30">
              Live writes
            </span>
          )}
          {actions}
        </div>
      </div>
    </header>
  );
}
