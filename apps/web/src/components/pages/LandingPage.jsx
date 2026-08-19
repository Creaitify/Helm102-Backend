import React from 'react';
import { useHelmStore } from '../../context/HelmStore';

export function LandingPage({ onOpenDataCenter }) {
  const { setActiveTab, startMission, isOrchestrating, currentRunState } = useHelmStore();

  const cards = [
    {
      id: 'analysis',
      icon: 'analytics',
      title: 'Analyze',
      text: 'Campaign performance, ROAS decay, and multi-channel insights',
      color: 'text-agent-blue',
    },
    {
      id: 'creative',
      icon: 'edit_document',
      title: 'Create',
      text: 'Compliant ad creatives and 9:16 video scripts that convert',
      color: 'text-agent-orange',
    },
    {
      id: 'budget',
      icon: 'tune',
      title: 'Optimize',
      text: 'Budget reallocation and ROAS-maximizing recommendations',
      color: 'text-agent-green',
    },
    {
      id: 'approval',
      icon: 'policy',
      title: 'Govern',
      text: 'Human-in-the-loop signoff with immutable audit trails',
      color: 'text-agent-purple',
    },
  ];

  const quickObjectives = [
    'Analyze campaign performance, prune fatigued assets, and scale top winners.',
    'Generate compliant 9:16 video storyboard and headlines for SIP Growth.',
    'Reallocate budget to high ROAS channels within the ±25% daily limit.',
  ];

  return (
    <div className="text-center max-w-4xl mx-auto w-full flex flex-col items-center py-6">
      {/* Hero Icon */}
      <div className="w-24 h-24 bg-primary-container text-on-primary-container rounded-3xl flex items-center justify-center mb-8 shadow-sm rotate-3 hover:rotate-0 transition-transform duration-300">
        <span className="material-symbols-outlined icon-fill text-[48px]">sailing</span>
      </div>

      {/* Hero Headings */}
      <h1 className="font-headline-xl text-3xl md:text-4xl font-black text-on-surface mb-3 tracking-tight">
        Welcome to HELM
      </h1>
      <p className="text-body-md text-on-surface-variant max-w-md mx-auto mb-10 text-sm md:text-base leading-relaxed">
        AI-powered marketing operations control plane for financial companies. Governed, compliant, and grounded.
      </p>

      {/* 4 Capability Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 w-full mb-10">
        {cards.map((card) => (
          <div
            key={card.title}
            onClick={() => setActiveTab(card.id)}
            className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-5 hover:border-primary/40 hover:shadow-md transition-all cursor-pointer group flex flex-col h-full text-left active:scale-[0.98]"
          >
            <span
              className={`material-symbols-outlined ${card.color} mb-3 group-hover:scale-110 transition-transform text-[28px]`}
            >
              {card.icon}
            </span>
            <h3 className="font-headline-md font-bold text-sm text-on-surface mb-1.5">{card.title}</h3>
            <p className="text-[12px] text-on-surface-variant leading-relaxed">{card.text}</p>
          </div>
        ))}
      </div>

      {/* Quick Launch Mission Prompts */}
      <div className="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-5 text-left mb-6">
        <div className="flex items-center justify-between mb-3">
          <span className="font-label-mono text-[11px] text-outline uppercase font-bold tracking-wider">
            Quick Launch Missions
          </span>
          <button
            onClick={onOpenDataCenter}
            className="font-label-mono text-[11px] text-primary hover:underline flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-[14px]">cloud_upload</span>
            Upload Real Data (BYOD)
          </button>
        </div>

        <div className="space-y-2">
          {quickObjectives.map((obj, i) => (
            <button
              key={i}
              disabled={isOrchestrating}
              onClick={() => {
                startMission(obj);
                setActiveTab('analysis');
              }}
              className="w-full text-left p-3 rounded-lg bg-surface-container-low hover:bg-surface-container hover:text-primary transition-colors text-xs flex items-center justify-between group"
            >
              <span className="text-on-surface group-hover:text-primary font-medium">{obj}</span>
              <span className="material-symbols-outlined text-[16px] text-outline group-hover:text-primary">
                play_circle
              </span>
            </button>
          ))}
        </div>
      </div>

      <p className="text-xs text-on-surface-variant">
        Type an instruction below or select a capability above to begin.
      </p>
    </div>
  );
}
