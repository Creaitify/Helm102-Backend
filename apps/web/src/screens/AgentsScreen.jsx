/**
 * Agents — a dedicated console per specialist.
 *
 * Not a chat window: each agent gets its own workspace with a stated
 * capability, one-click tasks it is actually good at, and a transcript of
 * structured results. Picking an agent is the primary act; typing is optional.
 */

import React, { useEffect, useRef, useState } from 'react';
import { useHelm } from '../store';
import { ContextBar } from '../components/Shell';
import { BlockRenderer } from '../components/blocks/BlockRenderer';
import { Button, Chip, EmptyState, Icon, Spinner, formatTime } from '../components/ui';

const ACCENTS = {
  governor: { ring: 'border-purple-200', bg: 'bg-purple-50', text: 'text-purple-700', dot: 'bg-purple-500' },
  analyst: { ring: 'border-blue-200', bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-500' },
  creative: { ring: 'border-fuchsia-200', bg: 'bg-fuchsia-50', text: 'text-fuchsia-700', dot: 'bg-fuchsia-500' },
  media_buyer: { ring: 'border-orange-200', bg: 'bg-orange-50', text: 'text-orange-700', dot: 'bg-orange-500' },
  compliance: { ring: 'border-green-200', bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },
};

/** Tasks each specialist is genuinely good at — the fast path to a result. */
const TASKS = {
  analyst: [
    'Which campaigns should I cut and which should I scale?',
    'What is driving my CPA this period?',
    'Which campaigns are fatiguing, and what is the evidence?',
    'Compare Google Ads and Meta efficiency for me',
  ],
  media_buyer: [
    'Propose an optimal budget reallocation',
    'Move spend toward the highest-ROAS campaigns',
    'Cut budget on decaying campaigns and show the conservation proof',
  ],
  creative: [
    'Write 3 ad variations for our SIP portfolio review service',
    'Write compliant copy for an ELSS tax-saving campaign',
    'Write retargeting copy for users who dropped out of KYC',
  ],
  compliance: [
    'Get guaranteed returns with zero risk on your investment today',
    'Our fund delivers the highest returns in the category — invest now',
    'Start a SIP from ₹500 a month and build wealth over time',
  ],
  governor: [
    'Reduce CPA and scale winning campaigns while staying compliant',
    'Refresh fatigued creative and rebalance budget toward what converts',
  ],
};

const PLACEHOLDERS = {
  compliance: 'Paste the ad copy you want scanned against SEBI rules…',
  creative: 'Describe the campaign you need copy for…',
  analyst: 'Ask anything about campaign performance…',
  media_buyer: 'Ask about budget allocation…',
  governor: 'State the business objective…',
};

export function AgentsScreen() {
  const { agentRoster, activeAgent, set } = useHelm();
  const agent = agentRoster.find((a) => a.id === activeAgent) || agentRoster[0];

  if (!agentRoster.length) {
    return (
      <>
        <ContextBar title="Agents" />
        <div className="flex justify-center py-24 text-primary">
          <Spinner className="w-7 h-7" />
        </div>
      </>
    );
  }

  return (
    <>
      <ContextBar
        title="Agents"
        subtitle="Put one specialist on a task and get a structured answer back"
      />

      <div className="p-4 sm:p-7 max-w-[1400px]">
        {/* Agent picker */}
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3 mb-6">
          {agentRoster.map((a) => (
            <AgentCard
              key={a.id}
              agent={a}
              active={a.id === agent?.id}
              onSelect={() => set({ activeAgent: a.id })}
            />
          ))}
        </div>

        {agent && <AgentConsole agent={agent} />}
      </div>
    </>
  );
}

function AgentCard({ agent, active, onSelect }) {
  const accent = ACCENTS[agent.id] || ACCENTS.analyst;
  const { agentBusy } = useHelm();
  const busy = agentBusy === agent.id;

  return (
    <button
      onClick={onSelect}
      aria-pressed={active}
      className={`card p-4 text-left transition-all focus-ring ${
        active ? 'border-primary ring-1 ring-primary/30 shadow-sm' : 'hover:border-outline-variant'
      }`}
    >
      <div className="flex items-center gap-2.5 mb-2">
        <span
          className={`w-9 h-9 rounded-lg grid place-items-center border shrink-0 ${accent.bg} ${accent.ring} ${accent.text} ${
            busy ? 'animate-pulse' : ''
          }`}
        >
          <Icon name={agent.icon} size={19} fill />
        </span>
        <span className="min-w-0">
          <span className="block font-headline text-body-md font-semibold text-on-surface truncate">
            {agent.label}
          </span>
          <span className="block rail-label truncate">{busy ? 'Working…' : agent.role}</span>
        </span>
      </div>
      <p className="text-body-sm text-on-surface-variant leading-snug line-clamp-2">
        {agent.description}
      </p>
    </button>
  );
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function AgentConsole({ agent }) {
  const { agentThreads, agentBusy, askAgent, clearAgent } = useHelm();
  const thread = agentThreads[agent.id] || [];
  const [draft, setDraft] = useState('');
  const [attachment, setAttachment] = useState(null);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef(null);
  const endRef = useRef(null);
  const accent = ACCENTS[agent.id] || ACCENTS.analyst;
  const busy = agentBusy === agent.id;

  useEffect(() => {
    if (thread.length) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [thread.length, busy]);

  const handleFile = (file) => {
    if (!file) return;
    const name = file.name.toLowerCase();
    const valid =
      name.endsWith('.csv') ||
      name.endsWith('.xlsx') ||
      name.endsWith('.xls') ||
      name.endsWith('.json') ||
      name.endsWith('.pdf');
    if (!valid) {
      alert('Please upload a .csv, .xlsx, .xls, .json, or .pdf dataset.');
      return;
    }
    if (file.size === 0) {
      alert('The selected file is empty. Please upload a dataset or document with content.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      setAttachment({
        file,
        filename: file.name,
        file_content: e.target.result,
        size: file.size,
      });
    };
    reader.readAsDataURL(file);
  };

  const handleFileSelect = (event) => {
    const file = event.target.files?.[0];
    if (file) handleFile(file);
    event.target.value = '';
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const removeAttachment = () => {
    setAttachment(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const submit = (event) => {
    event?.preventDefault();
    if ((!draft.trim() && !attachment) || busy) return;
    askAgent(agent.id, draft, attachment);
    setDraft('');
    setAttachment(null);
  };

  return (
    <section className="card overflow-hidden">
      <header className="px-5 py-4 border-b border-outline-variant/40 flex flex-wrap items-center gap-3">
        <span className={`w-10 h-10 rounded-xl grid place-items-center border ${accent.bg} ${accent.ring} ${accent.text}`}>
          <Icon name={agent.icon} size={21} fill />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-headline text-headline-md text-on-surface">{agent.label}</h2>
          <p className="text-body-sm text-on-surface-variant">{agent.description}</p>
        </div>
        {thread.length > 0 && (
          <Button variant="ghost" size="sm" icon="delete_sweep" onClick={() => clearAgent(agent.id)}>
            Clear
          </Button>
        )}
      </header>

      {/* Suggested prompts */}
      {thread.length === 0 && (
        <div className="p-5 border-b border-outline-variant/30 bg-surface-container-low/30">
          <p className="rail-label mb-2">One-click tasks</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {(TASKS[agent.id] || []).map((task) => (
              <button
                key={task}
                onClick={() => askAgent(agent.id, task)}
                disabled={busy}
                className="text-left text-body-sm p-3 rounded-lg border border-outline-variant/40 bg-surface hover:border-primary hover:bg-primary/5 transition-all text-on-surface focus-ring"
              >
                {task}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Transcript */}
      <div className="p-5 min-h-[300px] max-h-[550px] overflow-y-auto">
        {thread.length === 0 ? (
          <EmptyState
            icon={agent.icon}
            title={`${agent.label} is ready`}
            description={`Pick a one-click task above, attach a dataset (.csv, .xlsx, .json, .pdf), or type an objective below.`}
          />
        ) : (
          <div className="space-y-7">
            {thread.map((entry, index) => (
              <Entry key={index} entry={entry} agent={agent} accent={accent} />
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Composer */}
      <form
        onSubmit={submit}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          if (!e.currentTarget.contains(e.relatedTarget)) {
            setDragging(false);
          }
        }}
        onDrop={handleDrop}
        className={`px-5 py-4 border-t border-outline-variant/40 bg-surface-container-low/40 transition-colors ${
          dragging ? 'bg-primary/10 border-primary ring-2 ring-primary/20' : ''
        }`}
      >
        {/* Attachment chip */}
        {attachment && (
          <div className="flex items-center gap-2 mb-3 px-3 py-1.5 rounded-lg bg-surface-container-highest border border-outline-variant/60 w-fit max-w-full shadow-sm">
            <Icon name="attach_file" size={16} className="text-primary shrink-0" />
            <span className="font-mono text-body-sm text-on-surface truncate">
              {attachment.filename}
            </span>
            <span className="rail-label text-[11px] text-on-surface-variant">
              ({formatBytes(attachment.size)})
            </span>
            <button
              type="button"
              onClick={removeAttachment}
              className="p-1 rounded-md text-outline hover:text-error hover:bg-surface-container transition-colors ml-1 focus-ring"
              title="Remove attachment"
              aria-label="Remove attachment"
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        )}

        <div className="flex items-end gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".csv,.xlsx,.xls,.json,.pdf,text/csv,application/json,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
            className="hidden"
            aria-label="Upload dataset or document"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={busy}
            title="Attach dataset or document (.csv, .xlsx, .xls, .json, .pdf)"
            aria-label="Attach dataset or document"
            className="p-2.5 rounded-lg border border-outline-variant/50 bg-surface-container-lowest text-on-surface-variant hover:text-primary hover:border-primary/50 transition-colors focus-ring shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Icon name="attach_file" size={20} />
          </button>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) submit(event);
            }}
            rows={agent.id === 'compliance' ? 3 : 1}
            placeholder={
              attachment
                ? `Ask ${agent.label} about ${attachment.filename}…`
                : (PLACEHOLDERS[agent.id] || 'Ask this agent…')
            }
            aria-label={`Ask ${agent.label}`}
            className="flex-1 resize-none rounded-lg border border-outline-variant/50 bg-surface-container-lowest px-3.5 py-2.5 text-body-md text-on-surface placeholder:text-outline focus-ring focus:border-primary/50 max-h-40"
          />
          <Button
            type="submit"
            icon={busy ? undefined : 'send'}
            disabled={(!draft.trim() && !attachment) || busy}
          >
            {busy ? <Spinner /> : 'Ask'}
          </Button>
        </div>
      </form>
    </section>
  );
}

function Entry({ entry, agent, accent }) {
  if (entry.kind === 'question') {
    return (
      <div className="flex items-start gap-2.5">
        <span className="w-6 h-6 rounded-full bg-surface-container grid place-items-center shrink-0 mt-0.5">
          <Icon name="person" size={14} className="text-on-surface-variant" />
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-body-md text-on-surface font-medium leading-relaxed">
            {entry.text}
          </p>
          {entry.attachmentName && (
            <div className="inline-flex items-center gap-1.5 mt-1.5 px-2.5 py-1 rounded-md bg-surface-container border border-outline-variant/40 text-body-sm text-on-surface-variant">
              <Icon name="attach_file" size={14} className="text-primary shrink-0" />
              <span className="font-mono text-xs truncate">{entry.attachmentName}</span>
            </div>
          )}
        </div>
        <span className="rail-label shrink-0 pt-1">{formatTime(entry.at)}</span>
      </div>
    );
  }


  if (entry.kind === 'pending') {
    return (
      <div className="flex items-center gap-3 pl-8.5">
        <span className="flex gap-1" aria-label="Working">
          {[0, 1, 2].map((dot) => (
            <span key={dot} className="typing-dot w-1.5 h-1.5 rounded-full bg-primary" />
          ))}
        </span>
        <span className="text-body-sm text-on-surface-variant">
          {agent.label} is reasoning over your account data…
        </span>
      </div>
    );
  }

  if (entry.kind === 'error') {
    return (
      <div className="rounded-xl border border-error/30 bg-error-container p-4 flex gap-3">
        <Icon name="error" size={18} className="text-error shrink-0 mt-0.5" fill />
        <div>
          <p className="font-headline text-body-md font-semibold text-on-error-container">
            {agent.label} could not complete this
          </p>
          <p className="text-body-sm text-on-error-container/90 mt-0.5">{entry.text}</p>
        </div>
      </div>
    );
  }

  const envelope = entry.envelope || {};
  const meta = envelope.meta || {};

  return (
    <article>
      <div className="flex items-center gap-2 mb-2.5">
        <span className={`w-6 h-6 rounded-md grid place-items-center border ${accent.bg} ${accent.ring} ${accent.text}`}>
          <Icon name={agent.icon} size={14} fill />
        </span>
        <span className="font-headline text-body-md font-semibold text-on-surface">
          {envelope.agent_label || agent.label}
        </span>
        {meta.gateway_mode === 'replay' && (
          <Chip
            label="Replay"
            className="!bg-surface-container !text-outline !border-outline-variant/40"
          />
        )}
        {meta.data_source && meta.data_source !== 'live' && <Chip label={`${meta.data_source} data`} />}
        <span className="rail-label ml-auto">{formatTime(entry.at)}</span>
      </div>

      {envelope.message && (
        <div className="card p-4 mb-4 border-l-2 border-l-primary">
          <p className="text-body-md text-on-surface-variant leading-relaxed whitespace-pre-wrap">
            {envelope.message}
          </p>
        </div>
      )}

      <BlockRenderer blocks={envelope.blocks} />

      {envelope.sources?.length > 0 && (
        <details className="mt-4 card p-3 group">
          <summary className="cursor-pointer select-none flex items-center gap-2 rail-label focus-ring rounded">
            <Icon name="fact_check" size={15} className="text-viz-good" fill />
            Grounded in {envelope.sources.length} source
            {envelope.sources.length === 1 ? '' : 's'}
            <Icon
              name="expand_more"
              size={15}
              className="ml-auto transition-transform group-open:rotate-180"
            />
          </summary>
          <ul className="mt-3 space-y-2">
            {envelope.sources.map((source, index) => (
              <li
                key={index}
                className="flex items-start justify-between gap-3 text-body-sm border-t border-outline-variant/25 pt-2 first:border-0 first:pt-0"
              >
                <span>
                  <span className="block text-on-surface font-medium">{source.title}</span>
                  <span className="font-mono text-[11px] text-outline">{source.lines}</span>
                </span>
                {source.source && <Chip label={source.source} />}
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}
