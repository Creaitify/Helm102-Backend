import React, { useState, useRef } from 'react';
import { useHelmStore } from '../../context/HelmStore';

export function DataCenterModal({ isOpen, onClose }) {
  const {
    byodSnapshot,
    syntheticSnapshot,
    uploadByodFile,
    ingestByodUrl,
    clearByodData,
    generateSyntheticScenario,
    health,
  } = useHelmStore();

  const [activeTab, setActiveTab] = useState('upload');
  const [urlInput, setUrlInput] = useState('');
  const [scenario, setScenario] = useState('growth_and_fatigue');
  const [isProcessing, setIsProcessing] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const isRealData = health.data_source === 'byod' || byodSnapshot != null;

  const handleFileUpload = async (file) => {
    if (!file) return;
    setIsProcessing(true);
    setStatusMsg(null);

    try {
      const reader = new FileReader();
      const isBinary = file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.xls');

      reader.onload = async (e) => {
        try {
          let content;
          if (isBinary) {
            const arrayBuffer = e.target.result;
            const bytes = new Uint8Array(arrayBuffer);
            let binary = '';
            for (let i = 0; i < bytes.byteLength; i++) {
              binary += String.fromCharCode(bytes[i]);
            }
            content = window.btoa(binary);
          } else {
            content = e.target.result;
          }

          const res = await uploadByodFile(content, file.name, true);
          setStatusMsg({
            type: 'success',
            text: `Successfully ingested ${res.campaign_count} real campaigns from "${file.name}"!`,
          });
        } catch (err) {
          setStatusMsg({ type: 'error', text: `Upload failed: ${err.message}` });
        } finally {
          setIsProcessing(false);
        }
      };

      if (isBinary) {
        reader.readAsArrayBuffer(file);
      } else {
        reader.readAsText(file);
      }
    } catch (err) {
      setStatusMsg({ type: 'error', text: `Read error: ${err.message}` });
      setIsProcessing(false);
    }
  };

  const handleUrlSubmit = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    setIsProcessing(true);
    setStatusMsg(null);

    try {
      const res = await ingestByodUrl(urlInput.trim(), true);
      setStatusMsg({
        type: 'success',
        text: `Successfully ingested ${res.campaign_count} campaigns from URL!`,
      });
      setUrlInput('');
    } catch (err) {
      setStatusMsg({ type: 'error', text: `URL ingestion failed: ${err.message}` });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSeedSynthetic = async () => {
    setIsProcessing(true);
    setStatusMsg(null);
    await clearByodData();
    await generateSyntheticScenario(scenario, 60);
    setStatusMsg({ type: 'success', text: `Seeded "${scenario}" synthetic dataset into SQLite store!` });
    setIsProcessing(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="p-6 border-b border-outline-variant/20 flex items-center justify-between bg-surface-container-low/50">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary text-[24px]">database</span>
            <div>
              <h3 className="font-headline-lg text-lg font-bold text-on-surface">Marketing Data Ingestion Center</h3>
              <p className="text-xs text-on-surface-variant">Upload real CSV/Excel/JSON datasets or seed synthetic scenarios</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-surface-container text-outline hover:text-on-surface transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Status Chip */}
        <div className="px-6 pt-4">
          <div className={`p-3 rounded-xl border flex items-center justify-between text-xs ${
            isRealData
              ? 'bg-agent-green/10 border-agent-green/30 text-agent-green'
              : 'bg-primary/10 border-primary/20 text-primary'
          }`}>
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">
                {isRealData ? 'check_circle' : 'info'}
              </span>
              <span className="font-bold">
                {isRealData
                  ? `Active Dataset: Real User Data (${byodSnapshot?.campaign_count || byodSnapshot?.campaigns?.length || 0} campaigns)`
                  : 'Active Dataset: SQLite Synthetic Coherent Simulation'}
              </span>
            </div>
            {isRealData && (
              <button
                onClick={clearByodData}
                className="text-[11px] underline font-bold hover:text-error transition-colors"
              >
                Reset to Synthetic
              </button>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="px-6 pt-4">
          <div className="flex border-b border-outline-variant/20 gap-4">
            <button
              onClick={() => setActiveTab('upload')}
              className={`pb-2.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
                activeTab === 'upload'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-outline hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">upload_file</span>
              File Upload (CSV/XLSX/JSON)
            </button>
            <button
              onClick={() => setActiveTab('url')}
              className={`pb-2.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
                activeTab === 'url'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-outline hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">link</span>
              Remote URL Ingest
            </button>
            <button
              onClick={() => setActiveTab('synthetic')}
              className={`pb-2.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
                activeTab === 'synthetic'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-outline hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">science</span>
              Synthetic Presets
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'upload' && (
            <div className="space-y-4">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragOver(true);
                }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragOver(false);
                  if (e.dataTransfer.files?.[0]) handleFileUpload(e.dataTransfer.files[0]);
                }}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
                  isDragOver
                    ? 'border-primary bg-primary-fixed/20'
                    : 'border-outline-variant/40 bg-surface-container-low hover:bg-surface-container'
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  accept=".csv,.xlsx,.xls,.json"
                  onChange={(e) => {
                    if (e.target.files?.[0]) handleFileUpload(e.target.files[0]);
                  }}
                />
                <span className="material-symbols-outlined text-primary text-[36px] mb-2 block">
                  cloud_upload
                </span>
                <p className="font-bold text-sm text-on-surface mb-1">
                  {isProcessing ? 'Ingesting Real Marketing Dataset...' : 'Click or Drag & Drop File'}
                </p>
                <p className="text-xs text-outline">
                  Supports <strong>CSV, Excel (.xlsx, .xls), JSON</strong> multi-currency exports
                </p>
              </div>
            </div>
          )}

          {activeTab === 'url' && (
            <form onSubmit={handleUrlSubmit} className="space-y-4">
              <div>
                <label className="text-xs font-bold text-on-surface block mb-1.5">
                  Public Resource Endpoint (HTTP/HTTPS)
                </label>
                <input
                  type="url"
                  placeholder="https://example.com/campaign_metrics.csv"
                  className="w-full bg-surface-container-low border border-outline-variant/30 rounded-xl p-3 text-xs focus:ring-2 focus:ring-primary outline-none"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                />
              </div>
              <button
                type="submit"
                disabled={isProcessing || !urlInput.trim()}
                className="bg-primary hover:bg-on-primary-fixed-variant text-on-primary font-bold text-xs py-2.5 px-5 rounded-xl transition-all disabled:opacity-50"
              >
                {isProcessing ? 'Fetching URL...' : 'Fetch & Ingest Dataset'}
              </button>
            </form>
          )}

          {activeTab === 'synthetic' && (
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-on-surface block mb-1.5">
                  Select Coherent Scenario
                </label>
                <select
                  value={scenario}
                  onChange={(e) => setScenario(e.target.value)}
                  className="w-full bg-surface-container-low border border-outline-variant/30 rounded-xl p-3 text-xs focus:ring-2 focus:ring-primary outline-none"
                >
                  <option value="growth_and_fatigue">Search Growth + Meta Fatigue (Default)</option>
                  <option value="scale_winner">High-ROAS SIP Winner Scaling</option>
                  <option value="sebi_risk_scenario">SEBI Compliance Risk &amp; Loopback</option>
                  <option value="multi_channel_mix">Multi-Channel Balanced Mix</option>
                </select>
              </div>
              <button
                type="button"
                disabled={isProcessing}
                onClick={handleSeedSynthetic}
                className="bg-primary hover:bg-on-primary-fixed-variant text-on-primary font-bold text-xs py-2.5 px-5 rounded-xl transition-all disabled:opacity-50"
              >
                {isProcessing ? 'Generating...' : 'Seed Dataset into SQLite'}
              </button>
            </div>
          )}

          {/* Feedback message */}
          {statusMsg && (
            <div
              className={`mt-4 p-3 rounded-xl text-xs font-medium border ${
                statusMsg.type === 'success'
                  ? 'bg-agent-green/10 text-agent-green border-agent-green/30'
                  : 'bg-agent-rose/10 text-agent-rose border-agent-rose/30'
              }`}
            >
              {statusMsg.text}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
