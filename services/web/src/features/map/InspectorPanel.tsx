import React from "react";
import { CheckCircle2, Crosshair, Moon, ShieldAlert, Sun } from "lucide-react";

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
  is_lit?: boolean;
  lit_fraction?: number;
  longest_dark_hours?: number;
  is_psr?: boolean;
  time_series?: boolean[];
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
          <span>{inspection.is_hazard ? "TERRAIN HAZARD" : "SAFE TERRAIN"}</span>
        </div>
        <span className="text-[10px] font-mono">
          {inspection.is_hazard ? "SLOPE LIMIT EXCEEDED" : "TRAVERSABLE"}
        </span>
      </div>

      {/* Solar Illumination Status */}
      {inspection.is_lit !== undefined && (
        <div
          className={`flex items-center justify-between p-2 rounded border ${
            inspection.is_lit
              ? "bg-amber-950/30 border-amber-500/40 text-amber-200"
              : inspection.is_psr
              ? "bg-indigo-950/40 border-indigo-500/50 text-indigo-300"
              : "bg-slate-900/60 border-slate-700/60 text-slate-300"
          }`}
        >
          <div className="flex items-center gap-1.5 font-bold font-sans">
            {inspection.is_lit ? (
              <Sun className="w-4 h-4 text-amber-400 animate-pulse" aria-hidden="true" />
            ) : (
              <Moon className="w-4 h-4 text-indigo-400" aria-hidden="true" />
            )}
            <span>
              {inspection.is_lit ? "SUNLIT" : inspection.is_psr ? "PERMANENT SHADOW (PSR)" : "SHADOWED"}
            </span>
          </div>
          <span className="text-[10px] font-mono">
            {inspection.lit_fraction !== undefined ? `${(inspection.lit_fraction * 100).toFixed(0)}% LIT` : ""}
          </span>
        </div>
      )}

      {/* Sparkline series */}
      {inspection.time_series && inspection.time_series.length > 0 && (
        <div className="flex flex-col gap-1 bg-black/40 p-2 rounded border border-white/5">
          <div className="flex items-center justify-between text-[10px] text-gray-400">
            <span>Solar Series ({inspection.time_series.length}h)</span>
            {inspection.longest_dark_hours !== undefined && (
              <span className="text-rose-400">Max Dark: {inspection.longest_dark_hours.toFixed(0)}h</span>
            )}
          </div>
          <div className="flex items-center gap-0.5 h-3 w-full bg-black/60 p-0.5 rounded">
            {inspection.time_series.slice(0, 48).map((lit, idx) => (
              <div
                key={idx}
                className={`flex-1 h-full rounded-[1px] ${lit ? "bg-amber-400" : "bg-indigo-900"}`}
                title={`Hour ${idx}: ${lit ? "Lit" : "Dark"}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Coordinates */}
      <div className="space-y-1 bg-black/30 p-2.5 rounded border border-white/5">
        <div className="flex justify-between">
          <span className="text-gray-400">Polar Coord:</span>
          <span className="text-cyan-200">
            {inspection.lat_deg.toFixed(4)}°S, {inspection.lon_deg.toFixed(2)}°E
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Projected:</span>
          <span className="text-gray-300">
            X:{Math.round(inspection.x_m)}m Y:{Math.round(inspection.y_m)}m
          </span>
        </div>
      </div>

      {/* Topographic Metrics */}
      <div className="space-y-1.5 bg-black/30 p-2.5 rounded border border-white/5">
        <div className="flex justify-between">
          <span className="text-gray-400">Elevation:</span>
          <span className="text-cyan-300 font-bold">{inspection.elevation_m.toFixed(1)} m</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Slope:</span>
          <span className={inspection.slope_deg > 15 ? "text-rose-400 font-bold" : "text-emerald-400"}>
            {inspection.slope_deg.toFixed(1)}°
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Aspect Bearing:</span>
          <span className="text-gray-200">{getCompassHeading(inspection.aspect_deg)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Roughness (TRI):</span>
          <span className="text-gray-200">{inspection.roughness_m.toFixed(2)} m</span>
        </div>
      </div>
    </div>
  );
};
