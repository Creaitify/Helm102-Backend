/**
 * Renders the agent display grammar.
 *
 * The backend emits `blocks: [{type, ...}]` rather than agent-specific shapes,
 * so every agent — present and future — renders through this one switch. An
 * unknown block type degrades to a labelled JSON dump instead of crashing the
 * thread.
 */

import React, { useState } from 'react';
import { Chip, Icon } from '../ui';

export function BlockRenderer({ blocks = [] }) {
  if (!blocks.length) return null;
  return (
    <div className="space-y-4">
      {blocks.map((block, index) => (
        <Block key={`${block.type}-${index}`} block={block} />
      ))}
    </div>
  );
}

function Block({ block }) {
  switch (block.type) {
    case 'kpi_grid':
      return <KpiGrid block={block} />;
    case 'table':
      return <DataTable block={block} />;
    case 'bullets':
      return <Bullets block={block} />;
    case 'variations':
      return <Variations block={block} />;
    case 'policy_check':
      return <PolicyCheck block={block} />;
    case 'stepper':
      return <Stepper block={block} />;
    case 'findings':
      return <Findings block={block} />;
    case 'rewrite':
      return <Rewrite block={block} />;
    case 'text':
      return <FieldList block={block} />;
    default:
      return <UnknownBlock block={block} />;
  }
}

/* ------------------------------------------------------------------ */

function KpiGrid({ block }) {
  return (
    <section>
      {block.title && <BlockTitle>{block.title}</BlockTitle>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {block.items.map((item) => (
          <div key={item.label} className="card p-4">
            <p className="rail-label mb-1.5">{item.label}</p>
            <p className="font-headline text-headline-lg text-on-surface tabular-nums">
              {item.value}
            </p>
            {item.delta && (
              <p
                className={`mt-1 inline-flex items-center gap-0.5 font-mono text-[11px] font-semibold ${
                  item.delta_dir === 'up' ? 'text-green-600' : 'text-error'
                }`}
              >
                <Icon name={item.delta_dir === 'up' ? 'arrow_upward' : 'arrow_downward'} size={12} />
                {item.delta}
                <span className="text-outline font-normal ml-1">vs prior</span>
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function DataTable({ block }) {
  const columns = block.columns || [];
  const rows = block.rows || [];
  if (!rows.length) return null;

  const align = (col) =>
    col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left';

  return (
    <section>
      {block.title && <BlockTitle>{block.title}</BlockTitle>}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-body-sm border-collapse">
            <thead>
              <tr className="bg-surface-container-low border-b border-outline-variant/40">
                {columns.map((col) => (
                  <th
                    key={col.key}
                    scope="col"
                    className={`px-4 py-2.5 rail-label font-semibold whitespace-nowrap ${align(col)}`}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className="border-b border-outline-variant/25 last:border-0 hover:bg-surface-container-low/60 transition-colors"
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-4 py-2.5 text-on-surface-variant align-top ${align(col)} ${
                        col.align === 'right' ? 'tabular-nums font-medium' : ''
                      }`}
                    >
                      {col.kind === 'status' ? (
                        <Chip label={row[col.key]} />
                      ) : (
                        <span className={col.key === columns[0].key ? 'text-on-surface font-medium' : ''}>
                          {row[col.key] ?? '—'}
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
            {block.footer && (
              <tfoot>
                <tr className="bg-surface-container-low border-t border-outline-variant/40 font-semibold">
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-4 py-2.5 text-on-surface ${align(col)} ${
                        col.align === 'right' ? 'tabular-nums' : ''
                      }`}
                    >
                      {col.kind === 'status' && block.footer[col.key] ? (
                        <Chip label={block.footer[col.key]} />
                      ) : (
                        block.footer[col.key] ?? ''
                      )}
                    </td>
                  ))}
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </section>
  );
}

const BULLET_TONES = {
  pass: { icon: 'check_circle', className: 'text-green-600' },
  flag: { icon: 'warning', className: 'text-amber-600' },
  block: { icon: 'block', className: 'text-error' },
  info: { icon: 'lightbulb', className: 'text-primary' },
};

function Bullets({ block }) {
  const tone = BULLET_TONES[block.tone] || BULLET_TONES.info;
  return (
    <section>
      {block.title && <BlockTitle>{block.title}</BlockTitle>}
      <ul className="card p-4 space-y-2.5">
        {(block.items || []).map((item, index) => (
          <li key={index} className="flex gap-2.5 text-body-sm text-on-surface-variant leading-relaxed">
            <Icon name={tone.icon} size={16} className={`${tone.className} shrink-0 mt-0.5`} fill />
            <span>{typeof item === 'string' ? item : JSON.stringify(item)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Variations({ block }) {
  return (
    <section>
      {block.title && <BlockTitle>{block.title}</BlockTitle>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {(block.items || []).map((variation, index) => (
          <article key={index} className="card p-4 flex flex-col">
            <div className="flex items-start justify-between gap-2 mb-3">
              <div>
                <p className="font-headline text-body-md font-semibold text-on-surface">
                  {variation.title}
                </p>
                <p className="rail-label mt-0.5">{variation.subtitle}</p>
              </div>
              <Chip label={variation.status} />
            </div>

            <p className="font-headline text-headline-md text-on-surface leading-snug mb-2">
              {variation.headline}
            </p>
            <p className="text-body-sm text-on-surface-variant leading-relaxed flex-1">
              {variation.body}
            </p>

            {variation.cta && (
              <p className="mt-3 pt-3 border-t border-outline-variant/30 text-body-sm">
                <span className="rail-label">CTA</span>{' '}
                <span className="text-primary font-medium ml-1">{variation.cta}</span>
              </p>
            )}

            {variation.note && (
              <p className="mt-3 pt-3 border-t border-outline-variant/30 text-[11px] text-outline leading-snug italic">
                {variation.note}
              </p>
            )}

            {variation.violations?.length > 0 && (
              <ul className="mt-3 pt-3 border-t border-outline-variant/30 space-y-1.5">
                {variation.violations.map((violation, vIndex) => (
                  <li key={vIndex} className="flex gap-1.5 text-[11px] text-amber-700 leading-snug">
                    <Icon name="warning" size={13} className="shrink-0 mt-px" fill />
                    <span>{violation}</span>
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function PolicyCheck({ block }) {
  return (
    <section>
      {block.title && <BlockTitle>{block.title}</BlockTitle>}
      <div className="card p-4">
        <div className="flex items-center justify-between gap-3 mb-3 pb-3 border-b border-outline-variant/30">
          <span className="rail-label">Verdict</span>
          <Chip label={block.verdict} />
        </div>
        <ul className="space-y-2.5">
          {(block.items || []).map((item, index) => (
            <li key={index} className="flex items-center justify-between gap-3 text-body-sm">
              <span className="flex items-center gap-2 text-on-surface-variant">
                <Icon
                  name={
                    item.status === 'PASS'
                      ? 'check_circle'
                      : item.status === 'BLOCK'
                        ? 'block'
                        : 'warning'
                  }
                  size={16}
                  fill
                  className={
                    item.status === 'PASS'
                      ? 'text-green-600'
                      : item.status === 'BLOCK'
                        ? 'text-error'
                        : 'text-amber-600'
                  }
                />
                {item.label}
              </span>
              <Chip label={item.status} />
            </li>
          ))}
        </ul>

        {block.counts && (
          <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-outline-variant/30">
            {['PASS', 'FLAG', 'BLOCK'].map((key) => (
              <div key={key} className="text-center">
                <p
                  className={`font-headline text-headline-lg tabular-nums ${
                    key === 'PASS'
                      ? 'text-green-600'
                      : key === 'FLAG'
                        ? 'text-amber-600'
                        : 'text-error'
                  }`}
                >
                  {block.counts[key] ?? 0}
                </p>
                <p className="rail-label">{key}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function Stepper({ block }) {
  const steps = block.steps || [];
  return (
    <section>
      {block.title && <BlockTitle>{block.title}</BlockTitle>}
      <div className="card p-5">
        <ol className="flex items-start justify-between gap-1">
          {steps.map((step, index) => {
            const done = step.status === 'completed' || step.status === 'success';
            const active = step.status === 'in_progress' || step.status === 'running';
            return (
              <li key={index} className="flex-1 flex flex-col items-center text-center relative">
                {index > 0 && (
                  <span
                    className={`absolute top-4 right-1/2 w-full h-px ${
                      done ? 'bg-primary' : 'bg-outline-variant/50'
                    }`}
                    aria-hidden="true"
                  />
                )}
                <span
                  className={`relative z-10 w-8 h-8 rounded-full flex items-center justify-center border-2 ${
                    done
                      ? 'bg-primary border-primary text-on-primary'
                      : active
                        ? 'bg-surface-container-lowest border-primary text-primary animate-pulse-ring'
                        : 'bg-surface-container border-outline-variant/60 text-outline'
                  }`}
                >
                  <Icon name={done ? 'check' : active ? 'sync' : 'circle'} size={16} fill={done} />
                </span>
                <span className="mt-2 font-mono text-[10px] font-semibold text-on-surface leading-tight">
                  {step.label}
                </span>
                <span
                  className={`text-[10px] mt-0.5 capitalize ${
                    done ? 'text-green-600' : active ? 'text-primary' : 'text-outline'
                  }`}
                >
                  {done ? 'Completed' : active ? 'In progress' : String(step.status || 'waiting')}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}

const SEVERITY = {
  critical: { icon: 'error', dot: 'bg-viz-critical', chip: 'bg-red-50 text-red-800 border-red-200' },
  warning: { icon: 'warning', dot: 'bg-viz-warning', chip: 'bg-amber-50 text-amber-800 border-amber-200' },
  opportunity: { icon: 'trending_up', dot: 'bg-viz-good', chip: 'bg-green-50 text-green-800 border-green-200' },
  healthy: { icon: 'check_circle', dot: 'bg-viz-good', chip: 'bg-green-50 text-green-800 border-green-200' },
};

/** Ranked findings from the reasoning layer — severity is labelled, not just colored. */
function Findings({ block }) {
  return (
    <section>
      {block.title && <BlockTitle>{block.title}</BlockTitle>}
      <ul className="space-y-2">
        {(block.items || []).map((item, index) => {
          const tone = SEVERITY[item.severity] || SEVERITY.warning;
          return (
            <li key={index} className="card p-4 flex gap-3">
              <span className={`w-1 rounded-full shrink-0 ${tone.dot}`} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <Icon name={tone.icon} size={16} className="shrink-0" fill />
                  <span className="font-headline text-body-md font-semibold text-on-surface">
                    {item.title}
                  </span>
                  <span className={`chip border ${tone.chip}`}>{item.severity}</span>
                </div>
                <p className="text-body-sm text-on-surface-variant leading-relaxed">{item.detail}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Original vs compliant rewrite, side by side. */
function Rewrite({ block }) {
  return (
    <section>
      {block.title && <BlockTitle>{block.title}</BlockTitle>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="card p-4 border-error/30">
          <p className="rail-label mb-2 flex items-center gap-1.5">
            <Icon name="block" size={14} className="text-error" fill /> As submitted
          </p>
          <p className="text-body-sm text-on-surface-variant leading-relaxed whitespace-pre-wrap">
            {block.original}
          </p>
        </div>
        <div className="card p-4 border-green-300 bg-green-50/40">
          <p className="rail-label mb-2 flex items-center gap-1.5">
            <Icon name="check_circle" size={14} className="text-viz-good" fill /> Compliant rewrite
          </p>
          <p className="text-body-sm text-on-surface leading-relaxed whitespace-pre-wrap">
            {block.revised}
          </p>
        </div>
      </div>
    </section>
  );
}

function FieldList({ block }) {
  return (
    <section>
      {block.title && <BlockTitle>{block.title}</BlockTitle>}
      <dl className="card p-4 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
        {(block.fields || []).map((field, index) => (
          <div key={index}>
            <dt className="rail-label mb-0.5">{field.label}</dt>
            <dd className="text-body-sm text-on-surface-variant leading-relaxed">{field.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function UnknownBlock({ block }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="card p-3" open={open} onToggle={(event) => setOpen(event.target.open)}>
      <summary className="cursor-pointer rail-label select-none">
        Raw block: {block.type || 'unknown'}
      </summary>
      <pre className="mt-2 text-[11px] font-mono text-on-surface-variant overflow-x-auto whitespace-pre-wrap">
        {JSON.stringify(block, null, 2)}
      </pre>
    </details>
  );
}

function BlockTitle({ children }) {
  return <h4 className="font-headline text-body-md font-semibold text-on-surface mb-2">{children}</h4>;
}
