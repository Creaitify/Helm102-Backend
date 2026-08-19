import React from 'react';
import { useHelmStore } from '../../context/HelmStore';

export function CreativePage() {
  const { currentRunState } = useHelmStore();
  const pkg =
    currentRunState?.agent_reports?.creative ||
    currentRunState?.proposal?.creative_package;

  const brief = pkg?.brief || {
    core_angle: 'Disciplined Systematic SIP for Long-term Wealth',
    target_audience: 'Urban professionals aged 25-40 looking for automated investment growth.',
    pain_point: 'Market timing anxiety and idle savings in low-yield accounts.',
    value_proposition: 'Start automated index fund SIPs from ₹500/month with zero commission.',
  };

  const script = pkg?.script || {
    duration_seconds: 30,
    hook_3s: 'Still leaving your savings idle in a low-interest account?',
    problem_solution: 'Every month of delay costs long-term compounding. Automate your index SIP in 2 minutes.',
    scenes: [
      {
        timestamp_range: '0-3s',
        visual_cue: 'Person looking anxious at bank savings interest alert.',
        on_screen_text: 'Idle cash losing value?',
        audio_spoken: 'Still leaving your hard-earned money idle?',
      },
      {
        timestamp_range: '3-15s',
        visual_cue: 'Clean mobile app screen demonstrating 1-tap SIP setup.',
        on_screen_text: 'Automate Index SIPs in 2 Mins',
        audio_spoken: 'With disciplined monthly SIPs, let compounding work for your future.',
      },
      {
        timestamp_range: '15-30s',
        visual_cue: 'Growth milestone chart and statutory risk disclaimer footer.',
        on_screen_text: 'Invest Smartly & Responsibly',
        audio_spoken: 'Mutual fund investments are subject to market risks. Read all scheme related documents carefully.',
      },
    ],
  };

  const variations = [
    {
      title: 'Benefit Led',
      text: pkg?.creative?.headline || 'Automate Disciplined SIPs for Long-Term Growth',
      subtext: pkg?.creative?.primary_text || 'Start with ₹500/month. Mutual fund investments are subject to market risks.',
      status: 'PASS',
      sColor: 'bg-[#E6F4EA] text-[#137333] border-[#A8DAB5]',
    },
    {
      title: 'Curiosity Led',
      text: pkg?.creative?.alternative_headlines?.[0] || 'See How Much Compounding Adds Over 10 Years',
      subtext: 'Automated index fund allocation tailored for your financial goals.',
      status: 'PASS',
      sColor: 'bg-[#E6F4EA] text-[#137333] border-[#A8DAB5]',
    },
    {
      title: 'Urgency Led',
      text: pkg?.creative?.alternative_headlines?.[1] || 'Start This Quarter with Zero Advisory Fees',
      subtext: 'Get your comprehensive investment health check before market close.',
      status: 'FLAG',
      sColor: 'bg-[#FEF7E0] text-[#E37400] border-[#FDE293]',
    },
  ];

  return (
    <div className="max-w-4xl mx-auto w-full flex flex-col gap-6 py-4">
      {/* Header */}
      <div className="border-b border-outline-variant/20 pb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="font-headline-xl text-xl font-bold text-on-surface">
            Ad Creative Generation
          </h2>
          <span className="px-2 py-0.5 rounded text-[10px] font-label-mono bg-tertiary-fixed/30 text-tertiary font-bold border border-tertiary-fixed-dim">
            Direct Creative Mode
          </span>
        </div>
      </div>

      {/* User Message Bubble */}
      <div className="flex gap-4 items-start">
        <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center overflow-hidden border border-outline-variant/30 text-xs font-bold text-on-surface">
          RM
        </div>
        <div className="flex-1">
          <div className="bg-surface p-4 rounded-xl border border-outline-variant/30 shadow-sm text-sm text-on-surface">
            Generate 3 ad variations and 9:16 video requirements for portfolio review service.
          </div>
        </div>
      </div>

      {/* Creative Agent Response */}
      <div className="flex gap-4 items-start">
        <div className="w-8 h-8 rounded-full bg-[#FFF5EC] border border-[#FFDCC6] flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined text-[18px] text-[#F97316]">palette</span>
        </div>
        <div className="flex-1 space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-headline-md text-sm font-bold text-on-surface">Creative Agent</span>
            <span className="text-[10px] text-outline font-label-mono uppercase">10:32 AM</span>
          </div>

          {/* 3 Variation Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {variations.map((v, i) => (
              <div
                key={i}
                className="bg-surface rounded-xl border border-outline-variant/30 shadow-sm p-4 flex flex-col h-full border-t-4 border-t-[#F97316]/40"
              >
                <div className="text-[10px] font-label-mono text-outline uppercase mb-1">
                  Variation {i + 1}
                </div>
                <div className="text-[11px] font-headline-md font-bold text-primary-container mb-2">
                  {v.title}
                </div>
                <h3 className="font-headline-md font-bold text-sm text-on-surface mb-2">{v.text}</h3>
                <p className="text-[11px] text-on-surface-variant leading-relaxed mb-4">{v.subtext}</p>
                <div className="mt-auto pt-3 border-t border-outline-variant/20">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-label-mono font-bold border ${v.sColor}`}>
                    {v.status}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* 9:16 Video Script Storyboard */}
          <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3 border-b border-outline-variant/20 pb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-purple-600">movie</span>
                <h4 className="font-headline-md text-sm font-bold text-on-surface">
                  9:16 Video Script Storyboard ({script.duration_seconds}s)
                </h4>
              </div>
              <span className="badge badge-purple text-[10px]">Aspect Ratio: 9:16</span>
            </div>

            <div className="mb-3 p-3 bg-purple-50 border border-purple-200 rounded-lg">
              <span className="text-[11px] font-bold text-purple-900 block mb-0.5">0-3s Hook:</span>
              <p className="text-xs text-purple-950 font-medium italic">"{script.hook_3s}"</p>
            </div>

            <div className="space-y-2">
              {script.scenes.map((s, i) => (
                <div
                  key={i}
                  className="bg-surface-container-low p-3 rounded-lg border border-outline-variant/20 text-xs"
                >
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-primary">{s.timestamp_range}</span>
                    <span className="font-label-mono text-[10px] text-outline">{s.on_screen_text}</span>
                  </div>
                  <p className="text-on-surface mb-1"><strong>Visual:</strong> {s.visual_cue}</p>
                  <p className="text-on-surface-variant"><strong>Audio:</strong> "{s.audio_spoken}"</p>
                </div>
              ))}
            </div>
          </div>

          {/* Compliance Footer */}
          <div className="flex items-center gap-2 text-[12px] text-secondary">
            <span className="material-symbols-outlined text-[14px] text-agent-green">check_circle</span>
            <span>Compliance Check Complete</span>
            <span className="text-outline-variant mx-1">•</span>
            <span>3/3 variations processed</span>
          </div>
        </div>
      </div>
    </div>
  );
}
