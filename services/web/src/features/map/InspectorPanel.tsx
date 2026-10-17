import React from "react";
import { Crosshair, ShieldAlert, CheckCircle2 } from "lucide-react";

export interface PointInspection {
  x_m: number;
  y_m: number;
  lat_deg: number;
  lon_deg: number;
  elevation_m: number;
  slope_deg: number;
  aspect_deg: number;
  roughness_m: number;
  is_hazard: boolean;
  feature_name?: string;
}

interface InspectorPanelProps {
  inspection: PointInspection | null;
}

function getCompassHeading(deg: number): string {
  if (deg < 0) return "Flat (-)";
  const cardinals = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const idx = Math.round(deg / 22.5) % 16;
  return `${deg.toFixed(1)}° (${cardinals[idx]})`;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({ inspection }) => {
  if (!inspection) {
    return (
      <div className="glass-panel p-3.5 w-72 text-xs flex items-center gap-2 text-gray-400">
        <Crosshair className="w-4 h-4 text-cyan-400 animate-pulse" aria-hidden="true" />
        <span>Hover or click map to inspect pixel terrain...</span>
      </div>
    );
  }

  return (
    <div className="glass-panel p-4 w-72 flex flex-col gap-3 text-xs font-mono">
      <div className="flex items-center justify-between border-b border-white/10 pb-2">
        <div className="flex items-center gap-1.5 text-cyan-300 font-semibold font-sans">
          <Crosshair className="w-4 h-4 text-cyan-400" aria-hidden="true" />
          <span>Point Inspector</span>
        </div>
        {inspection.feature_name && (
          <span className="badge badge-cyan text-[10px]">{inspection.feature_name}</span>
        )}
      </div>

      {/* Hazard Status Flag */}
      <div
        className={`flex items-center justify-between p-2 rounded border ${
          inspection.is_hazard
            ? "bg-rose-950/40 border-rose-500/40 text-rose-300"
            : "bg-emerald-950/40 border-emerald-500/40 text-emerald-300"
        }`}
      >
        <div className="flex items-center gap-1.5 font-bold font-sans">
          {inspection.is_hazard ? (
            <ShieldAlert className="w-4 h-4 text-rose-400" aria-hidden="true" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" aria-hidden="true" />
          )}
          <span>{inspection.is_hazard ? "HAZARD DETECTED" : "TRAVERSABLE"}</span>
        </div>
        <span className="text-[10px]">{inspection.is_hazard ? "Slope > Limit" : "Safe Zone"}</span>
      </div>

      {/* Numerical Telemetry */}
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div>
          <span className="text-gray-400 block text-[10px]">ELEVATION</span>
          <span className="font-semibold text-gray-100">{inspection.elevation_m.toFixed(1)} m</span>
        </div>
        <div>
          <span className="text-gray-400 block text-[10px]">SLOPE (HORN)</span>
          <span className={`font-semibold ${inspection.slope_deg > 15 ? "text-rose-400" : "text-cyan-300"}`}>
            {inspection.slope_deg.toFixed(1)}&deg;
          </span>
        </div>
        <div>
          <span className="text-gray-400 block text-[10px]">ASPECT</span>
          <span className="text-gray-200">{getCompassHeading(inspection.aspect_deg)}</span>
        </div>
        <div>
          <span className="text-gray-400 block text-[10px]">ROUGHNESS (TRI)</span>
          <span className="text-gray-200">{inspection.roughness_m.toFixed(2)} m</span>
        </div>
        <div className="col-span-2 pt-1 border-t border-white/5 flex justify-between text-[10px] text-gray-400">
          <span>{inspection.lat_deg.toFixed(4)}&deg;S, {inspection.lon_deg.toFixed(4)}&deg;E</span>
          <span>({(inspection.x_m/1000).toFixed(2)}km, {(inspection.y_m/1000).toFixed(2)}km)</span>
        </div>
      </div>
    </div>
  );
};
