import React, { useState } from 'react';
import { useHelmStore } from '../context/HelmStore';

export function TopBar() {
  const { health, switchModel, byodSnapshot } = useHelmStore();
  const [isGrounded, setIsGrounded] = useState(true);
  const [showModelMenu, setShowModelMenu] = useState(false);

  const handleModelChange = (modelVal) => {
    if (modelVal === 'replay') {
      switchModel('replay', 'deterministic-replay-v1');
    } else if (modelVal.startsWith('claude')) {
      switchModel('anthropic', modelVal);
    } else {
      switchModel('gemini', modelVal);
    }
    setShowModelMenu(false);
  };

  const activeModelDisplay =
    health.gateway_mode === 'replay'
      ? 'Offline Replay'
      : health.active_model === 'gemini-3.1-flash'
      ? 'Gemini 3.1 Flash'
      : health.active_model === 'gemini-3.5-flash'
      ? 'Gemini 3.5 Flash'
      : health.active_model === 'claude-3-5-sonnet-20241022'
      ? 'Claude 3.5 Sonnet'
      : (health.active_model || 'Gemini 3.1 Flash');

  const isRealData = health.data_source === 'byod' || byodSnapshot != null;

  return (
    <header
      className="fixed top-0 flex justify-between items-center w-full px-gutter h-16 ml-[280px] mr-[280px] bg-surface/80 backdrop-blur-md border-b border-outline-variant/30 z-40"
      style={{ width: 'calc(100% - 560px)' }}
    >
      {/* Search Input */}
      <div className="flex-1 max-w-2xl relative">
        <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[18px]">
          search
        </span>
        <input
          className="w-full bg-surface-container-low border border-outline-variant/30 rounded-full py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow text-on-surface placeholder:text-outline"
          placeholder="Search conversations, campaigns, docs..."
          type="text"
        />
      </div>

      {/* Action Controls & Profile */}
      <div className="flex items-center gap-4 ml-6">
        {/* Data Source Chip */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium cursor-pointer transition-colors ${
            isRealData
              ? 'bg-agent-green/10 border-agent-green/30 text-agent-green'
              : 'bg-surface-container-low border-outline-variant/20 text-on-surface-variant'
          }`}
          title={isRealData ? 'Using User Uploaded Real Marketing Dataset' : 'Using Coherent Synthetic Preset'}
        >
          <span className="material-symbols-outlined text-[16px] text-primary icon-fill">
            {isRealData ? 'cloud_done' : 'database'}
          </span>
          <span>{isRealData ? 'Real Data (BYOD)' : 'Synthetic Mode'}</span>
        </div>

        {/* Grounded Compliance Toggle */}
        <div
          onClick={() => setIsGrounded(!isGrounded)}
          className="flex items-center gap-2 bg-surface-container-low px-3 py-1.5 rounded-full border border-outline-variant/20 cursor-pointer hover:bg-surface-container transition-colors"
          title="Deterministic SEBI citation grounding & statutory verification"
        >
          <span
            className={`material-symbols-outlined text-[16px] icon-fill ${
              isGrounded ? 'text-green-600' : 'text-outline'
            }`}
          >
            verified
          </span>
          <span className="text-xs font-medium">Grounded</span>
          <div
            className={`w-8 h-4 rounded-full relative ml-1 transition-colors ${
              isGrounded ? 'bg-green-500' : 'bg-outline-variant'
            }`}
          >
            <div
              className={`absolute top-0.5 w-3 h-3 bg-white rounded-full shadow-sm transition-all ${
                isGrounded ? 'right-1' : 'left-1'
              }`}
            />
          </div>
        </div>

        {/* Model Gateway Selector */}
        <div className="relative">
          <button
            onClick={() => setShowModelMenu(!showModelMenu)}
            className="flex items-center gap-2 bg-surface-container-low px-3 py-1.5 rounded-full border border-outline-variant/20 cursor-pointer hover:bg-surface-container transition-colors focus:outline-none"
          >
            <span className="material-symbols-outlined text-[16px] text-primary">smart_toy</span>
            <span className="text-xs font-medium">{activeModelDisplay}</span>
            <span className="material-symbols-outlined text-[16px]">expand_more</span>
          </button>

          {showModelMenu && (
            <div className="absolute right-0 mt-2 w-56 bg-surface-container-lowest border border-outline-variant/30 rounded-xl shadow-lg py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="px-3 py-1 text-[10px] font-label-mono text-outline uppercase tracking-wider">
                Google Gemini Models
              </div>
              <button
                onClick={() => handleModelChange('gemini-3.1-flash')}
                className="w-full text-left px-4 py-2 text-xs hover:bg-surface-container-low flex items-center justify-between font-medium"
              >
                <span>Gemini 3.1 Flash (Default)</span>
                <span className="text-[10px] text-agent-green font-bold">Fast</span>
              </button>
              <button
                onClick={() => handleModelChange('gemini-3.5-flash')}
                className="w-full text-left px-4 py-2 text-xs hover:bg-surface-container-low flex items-center justify-between"
              >
                <span>Gemini 3.5 Flash</span>
                <span className="text-[10px] text-primary">New</span>
              </button>
              <button
                onClick={() => handleModelChange('gemini-2.5-flash')}
                className="w-full text-left px-4 py-2 text-xs hover:bg-surface-container-low"
              >
                Gemini 2.5 Flash
              </button>
              <button
                onClick={() => handleModelChange('gemini-2.5-pro')}
                className="w-full text-left px-4 py-2 text-xs hover:bg-surface-container-low"
              >
                Gemini 2.5 Pro
              </button>
              <div className="my-1 border-t border-outline-variant/20" />
              <div className="px-3 py-1 text-[10px] font-label-mono text-outline uppercase tracking-wider">
                Anthropic &amp; Replay
              </div>
              <button
                onClick={() => handleModelChange('claude-3-5-sonnet-20241022')}
                className="w-full text-left px-4 py-2 text-xs hover:bg-surface-container-low"
              >
                Claude 3.5 Sonnet
              </button>
              <button
                onClick={() => handleModelChange('replay')}
                className="w-full text-left px-4 py-2 text-xs hover:bg-surface-container-low text-outline-variant"
              >
                Offline Fast Replay
              </button>
            </div>
          )}
        </div>

        {/* User Profile Avatar */}
        <button
          className="w-8 h-8 rounded-full bg-tertiary-container text-on-tertiary-container flex items-center justify-center font-bold text-xs shadow-sm border border-outline-variant/20 hover:ring-2 hover:ring-primary/30 transition-all"
          title="Growth & Marketing Lead"
        >
          RM
        </button>
      </div>
    </header>
  );
}
