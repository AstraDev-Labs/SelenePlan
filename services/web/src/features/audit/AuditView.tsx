import React from "react";
import { Activity, ShieldCheck, Hash, Link2 } from "lucide-react";

export const AuditView: React.FC = () => {
  const auditEvents = [
    {
      seq: 104,
      event: "selene.terrain.analysis.completed.v1",
      actor: "service-worker-terrain",
      prev_hash: "a4f89d31...b01",
      curr_hash: "fe8912cd...c44",
      timestamp: "2026-10-18T00:58:34Z",
      status: "VERIFIED",
    },
    {
      seq: 103,
      event: "selene.dataset.registered.v1",
      actor: "steward-1",
      prev_hash: "983210ab...e12",
      curr_hash: "a4f89d31...b01",
      timestamp: "2026-10-18T00:58:33Z",
      status: "VERIFIED",
    },
    {
      seq: 102,
      event: "selene.user.login.v1",
      actor: "planner-1",
      prev_hash: "1248abcc...d88",
      curr_hash: "983210ab...e12",
      timestamp: "2026-10-18T00:58:20Z",
      status: "VERIFIED",
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-bold text-white">Immutable Audit Chain</h2>
          <p className="text-xs text-gray-400">Tamper-evident, forward-secure hash chained audit log (FR-34, SEC-07).</p>
        </div>
        <div className="flex items-center gap-2 bg-emerald-950/40 border border-emerald-500/30 px-3 py-1.5 rounded-lg text-xs text-emerald-300 font-mono">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Chain Integrity: 100% Verified (0 Breaches)</span>
        </div>
      </div>

      <div className="glass-panel overflow-hidden">
        <table className="w-full text-left text-xs font-sans">
          <thead className="bg-white/5 border-b border-white/10 text-gray-400 font-mono text-[11px]">
            <tr>
              <th className="p-4">Seq #</th>
              <th className="p-4">Event Type</th>
              <th className="p-4">Actor</th>
              <th className="p-4">Hash Link (H_prev -&gt; H_curr)</th>
              <th className="p-4">Timestamp (UTC)</th>
              <th className="p-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 font-mono">
            {auditEvents.map((ev) => (
              <tr key={ev.seq} className="hover:bg-white/5 transition-colors">
                <td className="p-4 text-cyan-300 font-bold">#{ev.seq}</td>
                <td className="p-4 font-sans font-medium text-white">
                  <div className="flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{ev.event}</span>
                  </div>
                </td>
                <td className="p-4 text-gray-300">{ev.actor}</td>
                <td className="p-4 text-gray-400 text-[10px]">
                  <div className="flex items-center gap-1">
                    <Hash className="w-3 h-3 text-gray-500" />
                    <span>{ev.prev_hash}</span>
                    <Link2 className="w-3 h-3 text-cyan-400 mx-1" />
                    <span className="text-gray-200">{ev.curr_hash}</span>
                  </div>
                </td>
                <td className="p-4 text-gray-400">{ev.timestamp}</td>
                <td className="p-4">
                  <span className="badge badge-emerald">{ev.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
