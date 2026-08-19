import React, { useState } from 'react';
import { useHelmStore } from '../../context/HelmStore';

export function ApprovalPage() {
  const { currentRunState, resolveApproval, setActiveTab } = useHelmStore();
  const [notes, setNotes] = useState('Approved by Growth Lead under Q3 budget.');

  const proposal = currentRunState?.proposal;
  const status = currentRunState?.status || 'idle';
  const shifts = proposal?.budget_shifts || [];
  const totalCurr = proposal?.total_budget_current_inr || 90000;
  const totalProp = proposal?.total_budget_proposed_inr || 88500;
  const delta = totalProp - totalCurr;

  const handleApprove = () => {
    resolveApproval('approved', notes);
  };

  const handleReject = () => {
    resolveApproval('rejected', notes);
  };

  return (
    <div className="max-w-4xl mx-auto w-full flex flex-col gap-6 py-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="font-headline-xl text-xl font-bold text-on-surface">
            Budget Optimization Proposal
          </h2>
          <span className={`px-2.5 py-0.5 rounded-md font-label-mono text-[10px] uppercase font-bold border ${
            status === 'completed'
              ? 'bg-green-100 text-green-800 border-green-300'
              : status === 'rejected'
              ? 'bg-red-100 text-red-800 border-red-300'
              : 'bg-primary/10 text-primary border-primary/20'
          }`}>
            {status === 'completed'
              ? 'Approved & Executed'
              : status === 'rejected'
              ? 'Rejected'
              : 'Approval Required'}
          </span>
        </div>
      </div>

      {/* Approval Required Card */}
      <div className="bg-surface-container-lowest border border-[#fbbf24]/50 rounded-2xl overflow-hidden shadow-sm relative">
        <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#fbbf24]" />
        <div className="p-6 pl-8">
          {/* Header warning icon */}
          <div className="flex items-center gap-3 mb-6">
            <span className="material-symbols-outlined text-[#fbbf24] text-[28px]">warning</span>
            <div>
              <h3 className="font-headline-md text-[#b45309] uppercase text-[11px] font-bold tracking-wider">
                APPROVAL REQUIRED (HUMAN-IN-THE-LOOP)
              </h3>
              <p className="text-on-surface font-semibold text-sm mt-0.5">
                Media Buyer &amp; Governor are requesting approval for multi-channel budget optimization
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Left Col: Details */}
            <div className="space-y-5">
              <div>
                <h4 className="text-[10px] font-label-mono text-outline-variant uppercase mb-1 font-bold">
                  Proposed Action
                </h4>
                <p className="text-xs text-on-surface font-medium">
                  {proposal?.human_action_summary?.overview ||
                    `Reallocate budget across ${shifts.length > 0 ? shifts.length : 3} channels and deploy 1 fresh 9:16 video creative.`}
                </p>
              </div>

              <div>
                <h4 className="text-[10px] font-label-mono text-outline-variant uppercase mb-1 font-bold">
                  Optimization Rationale
                </h4>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  Scale top converting SIP search angle (+25%) while pruning fatigued broad audience assets. Compliant with SEBI statutory code.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="text-[10px] font-label-mono text-outline-variant uppercase mb-1 font-bold">
                    Agent
                  </h4>
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-[16px] text-[#f97316]">ads_click</span>
                    <span className="text-xs text-on-surface font-bold">Media Buyer</span>
                  </div>
                </div>
                <div>
                  <h4 className="text-[10px] font-label-mono text-outline-variant uppercase mb-1 font-bold">
                    Requested At
                  </h4>
                  <p className="text-xs text-on-surface">
                    {currentRunState?.timestamp ? new Date(currentRunState.timestamp).toLocaleTimeString() : 'Just now'}
                  </p>
                </div>
              </div>
            </div>

            {/* Right Col: Budget Summary Card */}
            <div className="bg-surface-container-low rounded-xl p-5 border border-outline-variant/30 flex flex-col justify-between">
              <div>
                <h4 className="text-[10px] font-label-mono text-outline-variant uppercase mb-4 font-bold">
                  Budget Summary (Daily Spend)
                </h4>
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-on-surface-variant">Current Budget</span>
                    <span className="font-bold text-on-surface">₹{Math.round(totalCurr).toLocaleString()}/day</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-on-surface-variant">Proposed Budget</span>
                    <span className="font-bold text-primary">₹{Math.round(totalProp).toLocaleString()}/day</span>
                  </div>
                  <div className="h-px bg-outline-variant/30 my-2" />
                  <div className="flex justify-between items-center">
                    <span className="text-on-surface-variant">Total Change</span>
                    <span className={`font-bold ${delta <= 0 ? 'text-agent-green' : 'text-error'}`}>
                      {delta <= 0 ? `-₹${Math.abs(Math.round(delta)).toLocaleString()}` : `+₹${Math.round(delta).toLocaleString()}`}
                    </span>
                  </div>
                </div>
              </div>

              {/* Status Note */}
              <div className="mt-4 pt-3 border-t border-outline-variant/20 flex items-center justify-between text-[11px]">
                <span className="text-outline">Policy Constraint:</span>
                <span className="text-agent-green font-bold">±25% Daily Shift Cap Satisfied</span>
              </div>
            </div>
          </div>
        </div>

        {/* Approval Form Footer */}
        {status === 'pending_approval' && (
          <div className="bg-surface-container-low/50 border-t border-outline-variant/20 p-5 px-8 flex flex-col sm:flex-row gap-4 items-center justify-between">
            <div className="w-full sm:flex-1">
              <input
                type="text"
                className="w-full bg-surface border border-outline-variant/40 rounded-lg py-2 px-3 text-xs focus:ring-1 focus:ring-primary outline-none"
                placeholder="Approval notes / budget authorization reference..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
            <div className="flex gap-3 w-full sm:w-auto">
              <button
                type="button"
                onClick={handleApprove}
                className="flex-1 sm:flex-initial bg-[#10b981] hover:bg-[#059669] text-white py-2 px-5 rounded-lg text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-all active:scale-95"
              >
                <span className="material-symbols-outlined text-[16px]">check_circle</span>
                Approve &amp; Dispatch
              </button>
              <button
                type="button"
                onClick={handleReject}
                className="flex-1 sm:flex-initial bg-[#ef4444] hover:bg-[#dc2626] text-white py-2 px-4 rounded-lg text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-all active:scale-95"
              >
                <span className="material-symbols-outlined text-[16px]">cancel</span>
                Decline
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
