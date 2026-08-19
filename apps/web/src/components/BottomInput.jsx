import React, { useState, useRef } from 'react';
import { useHelmStore } from '../context/HelmStore';

export function BottomInput({ onOpenDataCenter }) {
  const { startMission, isOrchestrating, uploadByodFile } = useHelmStore();
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState('Full HELM Pipeline');
  const [showModeMenu, setShowModeMenu] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);

  const MODES = [
    { label: 'Full HELM Pipeline', color: 'bg-primary-container', dotColor: '#2170e4' },
    { label: 'Analyst Mode', color: 'bg-agent-blue', dotColor: '#3b82f6' },
    { label: 'Creative Studio', color: 'bg-agent-orange', dotColor: '#f97316' },
    { label: 'Media Buyer', color: 'bg-tertiary', dotColor: '#924700' },
  ];

  const currentModeObj = MODES.find((m) => m.label === mode) || MODES[0];

  const handleSend = (e) => {
    e?.preventDefault();
    if (!prompt.trim() || isOrchestrating) return;
    const finalObjective =
      mode === 'Full HELM Pipeline'
        ? prompt.trim()
        : `[${mode}] ${prompt.trim()}`;
    startMission(finalObjective);
    setPrompt('');
  };

  const handleFileAttach = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);

    try {
      const reader = new FileReader();
      const isBinary = file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.xls');

      reader.onload = async (event) => {
        try {
          let content;
          if (isBinary) {
            const arrayBuffer = event.target.result;
            const bytes = new Uint8Array(arrayBuffer);
            let binary = '';
            for (let i = 0; i < bytes.byteLength; i++) {
              binary += String.fromCharCode(bytes[i]);
            }
            content = window.btoa(binary);
          } else {
            content = event.target.result;
          }

          await uploadByodFile(content, file.name, true);
          alert(`✓ Ingested real marketing dataset "${file.name}"! Ready for Governor analysis.`);
        } catch (err) {
          alert(`File upload failed: ${err.message}`);
        } finally {
          setIsUploading(false);
        }
      };

      if (isBinary) {
        reader.readAsArrayBuffer(file);
      } else {
        reader.readAsText(file);
      }
    } catch (err) {
      alert(`File read error: ${err.message}`);
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed bottom-0 left-[280px] right-[280px] p-container-padding bg-gradient-to-t from-surface via-surface to-transparent z-30 flex justify-center pointer-events-none">
      <div className="w-full max-w-4xl bg-surface-container-lowest border border-outline-variant/40 rounded-2xl shadow-xl p-2 flex items-center gap-2 pointer-events-auto backdrop-blur-md relative">
        {/* Hidden File Input */}
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept=".csv,.xlsx,.xls,.json"
          onChange={handleFileAttach}
        />

        {/* Pipeline Mode Dropdown Button */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowModeMenu(!showModeMenu)}
            className="flex items-center gap-2 px-3 py-2 hover:bg-surface-container-low rounded-lg transition-colors border-r border-outline-variant/20 focus:outline-none"
          >
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: currentModeObj.dotColor }}
            />
            <span className="font-headline-md text-sm text-on-surface whitespace-nowrap">
              {currentModeObj.label}
            </span>
            <span className="material-symbols-outlined text-[16px] text-on-surface-variant">
              expand_more
            </span>
          </button>

          {showModeMenu && (
            <div className="absolute bottom-12 left-0 w-52 bg-surface-container-lowest border border-outline-variant/30 rounded-xl shadow-lg py-2 z-50 animate-in fade-in slide-in-from-bottom-2 duration-150">
              <div className="px-3 py-1 text-[10px] font-label-mono text-outline uppercase tracking-wider">
                Execution Routing
              </div>
              {MODES.map((m) => (
                <button
                  key={m.label}
                  type="button"
                  onClick={() => {
                    setMode(m.label);
                    setShowModeMenu(false);
                  }}
                  className="w-full text-left px-3 py-2 text-xs hover:bg-surface-container-low flex items-center gap-2.5"
                >
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: m.dotColor }} />
                  <span className="font-medium text-on-surface">{m.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Attach File Button */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="p-2 text-on-surface-variant hover:text-primary hover:bg-surface-container-low rounded-lg transition-colors ml-1 focus:outline-none"
          title="Upload real dataset (CSV, XLSX, JSON)"
          disabled={isUploading}
        >
          <span
            className={`material-symbols-outlined text-[20px] ${
              isUploading ? 'animate-bounce text-primary' : ''
            }`}
          >
            attach_file
          </span>
        </button>

        {/* Text Input */}
        <input
          className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-3 px-2 placeholder:text-outline text-on-surface outline-none"
          placeholder={
            isOrchestrating
              ? 'Governor relay is orchestrating...'
              : mode === 'Analyst Mode'
              ? 'Ask Analyst about ROAS decay, CPA metrics, campaign trends...'
              : mode === 'Creative Studio'
              ? 'Request compliant 9:16 video scripts, angles, and captions...'
              : mode === 'Media Buyer'
              ? 'Propose budget reallocation and scaling limits...'
              : 'Ask HELM anything or start a marketing mission...'
          }
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSend(e);
          }}
          disabled={isOrchestrating}
        />

        {/* Voice Input Button */}
        <button
          type="button"
          onClick={() => alert('Voice input available via Web Speech API.')}
          className="p-2 text-on-surface-variant hover:text-primary hover:bg-surface-container-low rounded-lg transition-colors focus:outline-none"
          title="Voice input"
        >
          <span className="material-symbols-outlined text-[20px]">mic</span>
        </button>

        {/* Send Button */}
        <button
          type="button"
          onClick={handleSend}
          disabled={!prompt.trim() || isOrchestrating}
          className={`bg-primary hover:bg-on-primary-fixed-variant text-on-primary px-5 py-2.5 rounded-lg font-headline-md text-sm flex items-center gap-2 transition-all shadow-sm ml-1 active:scale-95 ${
            !prompt.trim() || isOrchestrating ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          <span>Send</span>
          <span className="material-symbols-outlined text-[16px]">send</span>
        </button>
      </div>
    </div>
  );
}
