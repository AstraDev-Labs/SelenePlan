import React from "react";
import { Database, ExternalLink, ShieldCheck } from "lucide-react";

export const DatasetsView: React.FC = () => {
  const datasets = [
    {
      id: "lola-dem-polar",
      name: "LOLA Lunar South Pole DEM (20m)",
      source: "NASA PDS Geosciences Node",
      license: "NASA Open Data Policy (Public Domain)",
      resolution: "20.0 m/pixel",
      crs: "IAU_2015:30100 (Stereographic)",
      format: "Cloud-Optimized GeoTIFF (COG)",
      sha256: "d1cab69ffa3c984920612140bb0639d67eab8dda2a19efc73",
      status: "Ingested & Verified",
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-bold text-white">Ingested Mission Datasets</h2>
          <p className="text-xs text-gray-400">Cryptographically verified datasets for lunar surface analysis (FR-01, FR-02).</p>
        </div>
        <button className="btn-primary">
          <Database className="w-4 h-4" />
          <span>Ingest New Dataset</span>
        </button>
      </div>

      <div className="glass-panel overflow-hidden">
        <table className="w-full text-left text-xs font-sans">
          <thead className="bg-white/5 border-b border-white/10 text-gray-400 font-mono text-[11px]">
            <tr>
              <th className="p-4">Dataset Name</th>
              <th className="p-4">Provider / License</th>
              <th className="p-4">Resolution & CRS</th>
              <th className="p-4">Format & Checksum</th>
              <th className="p-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {datasets.map((ds) => (
              <tr key={ds.id} className="hover:bg-white/5 transition-colors">
                <td className="p-4 font-semibold text-white">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-cyan-400" />
                    <span>{ds.name}</span>
                  </div>
                </td>
                <td className="p-4">
                  <div className="text-gray-300 flex items-center gap-1">
                    <span>{ds.source}</span>
                    <ExternalLink className="w-3 h-3 text-gray-500" />
                  </div>
                  <span className="text-[10px] text-gray-500 block">{ds.license}</span>
                </td>
                <td className="p-4 font-mono text-gray-300">
                  <div>{ds.resolution}</div>
                  <div className="text-[10px] text-gray-500">{ds.crs}</div>
                </td>
                <td className="p-4 font-mono">
                  <span className="text-cyan-300">{ds.format}</span>
                  <span className="text-[10px] text-gray-500 block truncate w-40" title={ds.sha256}>
                    {ds.sha256.slice(0, 16)}...
                  </span>
                </td>
                <td className="p-4">
                  <span className="badge badge-emerald flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" />
                    <span>{ds.status}</span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
