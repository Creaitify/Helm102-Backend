import React from 'react';
import { useHelmStore } from '../../context/HelmStore';
import { Sparkles, Video, FileText, Share2, Tag } from 'lucide-react';

export function CreativeWorkspace() {
  const { currentRunState } = useHelmStore();
  const pkg =
    currentRunState?.agent_reports?.creative ||
    currentRunState?.proposal?.creative_package;

  if (!pkg) {
    return (
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Creative Studio Workspace</h3>
          <span className="badge badge-purple">4-Stage Pipeline</span>
        </div>
        <div className="empty-state-hint">
          No creative package generated yet. Launch a mission from the Governor HQ tab.
        </div>
      </div>
    );
  }

  const brief = pkg.brief || {};
  const script = pkg.script || {};
  const creative = pkg.creative || {};
  const captions = pkg.captions || {};

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 className="card-title">4-Stage Governed Creative Package</h3>
          <p className="banner-sub" style={{ marginTop: '0.2rem' }}>
            Structured creative generated via Gemini Model Gateway adhering to statutory SEBI standards.
          </p>
        </div>
        <span className="badge badge-purple">
          {pkg.generation_mode === 'llm' ? 'GEMINI GENERATED' : 'DETERMINISTIC FALLBACK'}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginTop: '1rem' }}>
        {/* Left: Stage 1 & Stage 2 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Stage 1: Brief */}
          <div className="card" style={{ padding: '1.25rem' }}>
            <div className="card-header" style={{ marginBottom: '0.5rem', paddingBottom: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <FileText className="w-4 h-4 text-blue-600" style={{ width: 16, height: 16 }} />
                <h4 className="card-title" style={{ fontSize: '0.9375rem' }}>Stage 1: Creative Brief</h4>
              </div>
              <span className="badge badge-blue">Strategic Angle</span>
            </div>
            <p style={{ fontSize: '0.875rem' }}><strong>Core Angle:</strong> {brief.core_angle}</p>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              <strong>Audience:</strong> {brief.target_audience}
            </p>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              <strong>Pain Point:</strong> {brief.pain_point}
            </p>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              <strong>Value Proposition:</strong> {brief.value_proposition}
            </p>
          </div>

          {/* Stage 2: 9:16 Video Script */}
          <div className="card" style={{ padding: '1.25rem' }}>
            <div className="card-header" style={{ marginBottom: '0.5rem', paddingBottom: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Video className="w-4 h-4 text-purple-600" style={{ width: 16, height: 16 }} />
                <h4 className="card-title" style={{ fontSize: '0.9375rem' }}>
                  Stage 2: 9:16 Video Script ({script.duration_seconds || 30}s)
                </h4>
              </div>
              <span className="badge badge-purple">{script.aspect_ratio || '9:16'}</span>
            </div>
            <p style={{ fontSize: '0.875rem', marginBottom: '0.5rem' }}>
              <strong>0-3s Hook:</strong> "{script.hook_3s}"
            </p>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
              {script.problem_solution}
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {(script.scenes || []).map((s, i) => (
                <div
                  key={i}
                  style={{
                    background: 'var(--bg-card-subtle)',
                    padding: '0.6rem 0.8rem',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                    <span className="badge badge-blue" style={{ fontSize: '0.7rem' }}>
                      {s.timestamp_range || `Scene ${i + 1}`}
                    </span>
                    <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {s.on_screen_text}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.8125rem' }}><strong>Visual:</strong> {s.visual_cue}</p>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    <strong>Audio:</strong> "{s.audio_spoken}"
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Stage 3 & Stage 4 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Stage 3: Ad Copy & Headlines */}
          <div className="card" style={{ padding: '1.25rem' }}>
            <div className="card-header" style={{ marginBottom: '0.5rem', paddingBottom: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles className="w-4 h-4 text-emerald-600" style={{ width: 16, height: 16 }} />
                <h4 className="card-title" style={{ fontSize: '0.9375rem' }}>
                  Stage 3: Ad Copy &amp; Headlines
                </h4>
              </div>
              <span className="badge badge-emerald">{creative.call_to_action || 'INVEST_NOW'}</span>
            </div>
            <h5 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--primary-blue)' }}>
              {creative.headline}
            </h5>
            <p style={{ fontSize: '0.875rem', marginTop: '0.5rem', lineHeight: 1.6 }}>
              {creative.primary_text}
            </p>

            <div style={{ marginTop: '0.75rem' }}>
              <span className="subheading" style={{ fontSize: '0.75rem' }}>
                Alternative Headlines:
              </span>
              <ul style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginLeft: '1rem', marginTop: '0.25rem' }}>
                {(creative.alternative_headlines || []).map((h, idx) => (
                  <li key={idx}>{h}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Stage 4: Social Platform Captions */}
          <div className="card" style={{ padding: '1.25rem' }}>
            <div className="card-header" style={{ marginBottom: '0.5rem', paddingBottom: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Share2 className="w-4 h-4 text-amber-600" style={{ width: 16, height: 16 }} />
                <h4 className="card-title" style={{ fontSize: '0.9375rem' }}>
                  Stage 4: Social Platform Captions
                </h4>
              </div>
              <span className="badge badge-amber">Multi-Platform</span>
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              <strong style={{ color: 'var(--text-main)' }}>Instagram:</strong> {captions.instagram_caption}
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              <strong style={{ color: 'var(--text-main)' }}>LinkedIn:</strong> {captions.linkedin_caption}
            </div>
            <div style={{ marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
              {(captions.hashtags || []).map((t, idx) => (
                <span key={idx} className="badge badge-blue" style={{ fontSize: '0.7rem' }}>
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
