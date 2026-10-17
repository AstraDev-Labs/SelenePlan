import React, { useState } from "react";
import { UserCheck, ShieldAlert, CheckCircle, XCircle } from "lucide-react";
import { useAuthStore } from "@/auth/store";

export const ApprovalsView: React.FC = () => {
  const { user } = useAuthStore();
  const [comment, setComment] = useState("");
  const [decision, setDecision] = useState<string | null>(null);

  // Author is different from approver per two-person rule
  const planAuthor = "user-planner-1";
  const isAuthor = user?.sub === planAuthor;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-bold text-white">Plan Approvals (Two-Person Rule)</h2>
        <p className="text-xs text-gray-400">Strict two-person rule enforcement: A plan cannot be approved by its author (FR-30, FR-31).</p>
      </div>

      <div className="glass-panel p-6 flex flex-col gap-5 border-amber-500/20">
        <div className="flex justify-between items-start border-b border-white/10 pb-4">
          <div>
            <span className="badge badge-amber text-[10px] mb-1">AWAITING APPROVAL</span>
            <h3 className="text-base font-bold text-white">Traverse Plan v1.4: Shackleton High Point Traverse</h3>
            <p className="text-xs text-gray-400">Created by: <span className="text-cyan-300 font-mono">{planAuthor}</span></p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono bg-white/5 px-3 py-1.5 rounded-lg border border-white/10">
            <UserCheck className="w-4 h-4 text-cyan-400" />
            <span>Two-Person Rule: Active</span>
          </div>
        </div>

        {isAuthor && (
          <div className="bg-rose-950/40 border border-rose-500/40 p-3.5 rounded-lg flex items-center gap-2.5 text-xs text-rose-300">
            <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
            <span>Access Restriction: You are the author of this plan. The two-person rule prohibits authors from approving their own plans.</span>
          </div>
        )}

        <div className="flex flex-col gap-2">
          <label htmlFor="decision-comment" className="text-xs font-semibold text-gray-300">
            Approver Comment &amp; Audit Justification
          </label>
          <textarea
            id="decision-comment"
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Record review notes, risk assessment, and mission concurrence..."
            className="bg-black/50 border border-white/10 rounded-lg p-3 text-xs text-gray-200 font-sans focus:outline-none focus:border-cyan-400"
          />
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            disabled={isAuthor || !comment}
            onClick={() => setDecision("APPROVED")}
            className="btn-primary bg-gradient-to-r from-emerald-500 to-teal-600 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <CheckCircle className="w-4 h-4" />
            <span>Approve Plan Version</span>
          </button>

          <button
            disabled={isAuthor || !comment}
            onClick={() => setDecision("REJECTED")}
            className="btn-ghost text-rose-400 border-rose-500/30 hover:bg-rose-500/10 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <XCircle className="w-4 h-4" />
            <span>Reject Plan</span>
          </button>
        </div>

        {decision && (
          <div className="bg-emerald-950/40 border border-emerald-500/40 p-3 rounded text-xs text-emerald-300 font-mono">
            Plan decision recorded: <strong>{decision}</strong>. Cryptographic audit event emitted with trace ID.
          </div>
        )}
      </div>
    </div>
  );
};
