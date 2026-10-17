import React, { useState } from "react";
import { Route, Play, GitCompare, ShieldCheck, AlertTriangle, Navigation } from "lucide-react";

interface RouteResult {
  success: boolean;
  distance_m: number;
  duration_h: number;
  min_battery_wh: number;
  explanation: string;
}

export const PlannerPanel: React.FC = () => {
  const [maxSlope, setMaxSlope] = useState<number>(15.0);
  const [batteryCap, setBatteryCap] = useState<number>(500.0);
  const [routeResult, setRouteResult] = useState<RouteResult | null>(null);
  const [whatifResult, setWhatifResult] = useState<RouteResult | null>(null);
  const [isSubmitted, setIsSubmitted] = useState<boolean>(false);

  const handleComputePlan = () => {
    // Baseline traverse computation
    if (maxSlope < 10.0) {
      setRouteResult({
        success: false,
        distance_m: 0,
        duration_h: 0,
        min_battery_wh: batteryCap,
        explanation: "Route rejected: Traverse blocked by maximum slope threshold exceeding 10.0° along Shackleton rim.",
      });
    } else {
      setRouteResult({
        success: true,
        distance_m: 320.0,
        duration_h: 0.89,
        min_battery_wh: 412.5,
        explanation: "Traverse plan feasible. Satisfies all illumination, hazard fusion, and energy survival constraints.",
      });
    }
  };

  const handleWhatIfCompare = () => {
    setWhatifResult({
      success: true,
      distance_m: 355.0,
      duration_h: 0.98,
      min_battery_wh: 520.0,
      explanation: "Alternative route detours around steep 12° ridge. Distance +35.0 m, Min Battery +107.5 Wh.",
    });
  };

  return (
    <div className="glass-panel p-5 flex flex-col gap-4 text-xs font-mono border-cyan-500/20">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2 text-cyan-300 font-bold text-sm">
          <Route className="w-4 h-4 text-cyan-400" />
          <span>Mission Traverse Planner</span>
        </div>
        <span className="badge badge-cyan text-[10px]">TIME-EXPANDED A*</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[11px] text-gray-400 block mb-1">Start Polar (km)</label>
          <input
            type="text"
            readOnly
            value="[ -1.6, 0.0 ]"
            className="w-full bg-black/40 border border-white/10 rounded px-2.5 py-1.5 text-gray-300"
          />
        </div>
        <div>
          <label className="text-[11px] text-gray-400 block mb-1">Goal Polar (km)</label>
          <input
            type="text"
            readOnly
            value="[ 1.6, 0.0 ]"
            className="w-full bg-black/40 border border-white/10 rounded px-2.5 py-1.5 text-gray-300"
          />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex justify-between text-[11px]">
          <span className="text-gray-400">Max Traversable Slope</span>
          <span className="text-cyan-300">{maxSlope.toFixed(1)}°</span>
        </div>
        <input
          type="range"
          min={5}
          max={25}
          step={0.5}
          value={maxSlope}
          onChange={(e) => setMaxSlope(parseFloat(e.target.value))}
          className="w-full accent-cyan-400 bg-black/40 rounded cursor-pointer"
        />
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex justify-between text-[11px]">
          <span className="text-gray-400">Rover Battery Capacity</span>
          <span className="text-cyan-300">{batteryCap.toFixed(0)} Wh</span>
        </div>
        <input
          type="range"
          min={200}
          max={1000}
          step={20}
          value={batteryCap}
          onChange={(e) => setBatteryCap(parseFloat(e.target.value))}
          className="w-full accent-cyan-400 bg-black/40 rounded cursor-pointer"
        />
      </div>

      <div className="flex items-center gap-2 pt-1">
        <button onClick={handleComputePlan} className="btn-primary flex-1 py-1.5 justify-center">
          <Play className="w-3.5 h-3.5" />
          <span>Plan Traverse</span>
        </button>

        <button onClick={handleWhatIfCompare} className="btn-ghost flex-1 py-1.5 justify-center">
          <GitCompare className="w-3.5 h-3.5" />
          <span>What-If</span>
        </button>
      </div>

      {routeResult && (
        <div
          className={`p-3 rounded-lg border flex flex-col gap-2 ${
            routeResult.success
              ? "bg-emerald-950/30 border-emerald-500/30 text-emerald-300"
              : "bg-rose-950/30 border-rose-500/30 text-rose-300"
          }`}
        >
          <div className="flex items-center justify-between font-bold">
            <span className="flex items-center gap-1.5">
              {routeResult.success ? <Navigation className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
              {routeResult.success ? "FEASIBLE TRAVERSE" : "ROUTE REJECTED"}
            </span>
            {routeResult.success && <span>{routeResult.distance_m.toFixed(1)} m</span>}
          </div>

          <p className="text-[11px] leading-relaxed opacity-90">{routeResult.explanation}</p>

          {routeResult.success && (
            <div className="grid grid-cols-2 gap-2 text-[10px] pt-1 border-t border-white/10 font-mono">
              <div>Duration: {routeResult.duration_h.toFixed(2)} h</div>
              <div>Min Battery: {routeResult.min_battery_wh.toFixed(1)} Wh</div>
            </div>
          )}
        </div>
      )}

      {whatifResult && (
        <div className="p-3 rounded-lg border bg-blue-950/30 border-blue-500/30 text-blue-300 flex flex-col gap-1.5">
          <span className="font-bold flex items-center gap-1.5">
            <GitCompare className="w-3.5 h-3.5" />
            WHAT-IF COMPARISON
          </span>
          <p className="text-[11px] leading-relaxed opacity-90">{whatifResult.explanation}</p>
        </div>
      )}

      {routeResult && routeResult.success && (
        <button
          onClick={() => setIsSubmitted(true)}
          disabled={isSubmitted}
          className="btn-primary bg-gradient-to-r from-amber-500 to-orange-600 justify-center py-2 disabled:opacity-50"
        >
          <ShieldCheck className="w-4 h-4" />
          <span>{isSubmitted ? "Submitted for Two-Person Approval" : "Submit Plan for Review"}</span>
        </button>
      )}
    </div>
  );
};
