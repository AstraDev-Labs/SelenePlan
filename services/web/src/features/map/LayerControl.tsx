import React from "react";
import { AlertTriangle, Cpu, Eye, EyeOff, Layers, Sliders } from "lucide-react";

export type Colormap = "viridis" | "magma" | "terrain" | "hazard";

export interface LayerState {
  showSlope: boolean;
  showAspect: boolean;
  showRoughness: boolean;
  showHazard: boolean;
  showHillshade: boolean;
  showIllumination: boolean;
  showPSR: boolean;
  showEarthVisibility: boolean;
  showMLHazard: boolean;
  showFusedHazard: boolean;
  mlConfidenceThreshold: number;
  colormap: Colormap;
  maxSlopeLimit: number;
}

interface LayerControlProps {
  layers: LayerState;
  onChange: (layers: LayerState) => void;
}

export const LayerControl: React.FC<LayerControlProps> = ({ layers, onChange }) => {
  const toggle = (key: keyof LayerState) => {
    onChange({
      ...layers,
      [key]: !layers[key],
    });
  };

  return (
    <aside aria-label="Map Layer Controls" className="glass-panel p-4 w-72 flex flex-col gap-4 text-xs font-sans">
      <div className="flex items-center justify-between border-b border-white/10 pb-2">
        <div className="flex items-center gap-2 text-cyan-300 font-semibold">
          <Layers className="w-4 h-4" aria-hidden="true" />
          <span>Active Map Layers</span>
        </div>
        <span className="badge badge-cyan text-[10px]">COG TILES</span>
      </div>

      {/* Layer Toggles */}
      <div className="flex flex-col gap-2">
        <button
          onClick={() => toggle("showFusedHazard")}
          className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
            layers.showFusedHazard ? "bg-amber-500/20 border border-amber-500/50 text-amber-200" : "bg-white/5 text-gray-400"
          }`}
        >
          <span className="font-semibold">Fused Hazard Map (FR-13)</span>
          {layers.showFusedHazard ? <Eye className="w-3.5 h-3.5 text-amber-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
        </button>

        <button
          onClick={() => toggle("showMLHazard")}
          className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
            layers.showMLHazard ? "bg-fuchsia-500/20 border border-fuchsia-500/40 text-fuchsia-200" : "bg-white/5 text-gray-400"
          }`}
        >
          <span>ML Crater Detection (Advisory)</span>
          {layers.showMLHazard ? <Eye className="w-3.5 h-3.5 text-fuchsia-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
        </button>

        <button
          onClick={() => toggle("showHazard")}
          className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
            layers.showHazard ? "bg-rose-500/15 border border-rose-500/30 text-rose-200" : "bg-white/5 text-gray-400"
          }`}
        >
          <span>Terrain Slope Hazard (&gt; {layers.maxSlopeLimit}&deg;)</span>
          {layers.showHazard ? <Eye className="w-3.5 h-3.5 text-rose-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
        </button>

        <button
          onClick={() => toggle("showEarthVisibility")}
          className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
            layers.showEarthVisibility ? "bg-cyan-500/20 border border-cyan-500/40 text-cyan-200" : "bg-white/5 text-gray-400"
          }`}
        >
          <span>Earth Visibility (Line of Sight)</span>
          {layers.showEarthVisibility ? <Eye className="w-3.5 h-3.5 text-cyan-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
        </button>

        <button
          onClick={() => toggle("showIllumination")}
          className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
            layers.showIllumination ? "bg-amber-500/20 border border-amber-500/40 text-amber-200" : "bg-white/5 text-gray-400"
          }`}
        >
          <span>Solar Illumination (Time Slice)</span>
          {layers.showIllumination ? <Eye className="w-3.5 h-3.5 text-amber-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
        </button>

        <button
          onClick={() => toggle("showPSR")}
          className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
            layers.showPSR ? "bg-indigo-500/20 border border-indigo-500/40 text-indigo-200" : "bg-white/5 text-gray-400"
          }`}
        >
          <span>Permanent Shadow (PSR)</span>
          {layers.showPSR ? <Eye className="w-3.5 h-3.5 text-indigo-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
        </button>

        <button
          onClick={() => toggle("showSlope")}
          className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
            layers.showSlope ? "bg-cyan-500/15 border border-cyan-500/30 text-cyan-200" : "bg-white/5 text-gray-400"
          }`}
        >
          <span>Slope (Horn 3x3)</span>
          {layers.showSlope ? <Eye className="w-3.5 h-3.5 text-cyan-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
        </button>

        <button
          onClick={() => toggle("showRoughness")}
          className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
            layers.showRoughness ? "bg-amber-500/15 border border-amber-500/30 text-amber-200" : "bg-white/5 text-gray-400"
          }`}
        >
          <span>Roughness (TRI)</span>
          {layers.showRoughness ? <Eye className="w-3.5 h-3.5 text-amber-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
        </button>

        <button
          onClick={() => toggle("showHillshade")}
          className={`flex items-center justify-between px-3 py-2 rounded-md transition-colors ${
            layers.showHillshade ? "bg-blue-500/15 border border-blue-500/30 text-blue-200" : "bg-white/5 text-gray-400"
          }`}
        >
          <span>DEM Hillshade</span>
          {layers.showHillshade ? <Eye className="w-3.5 h-3.5 text-blue-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
        </button>
      </div>

      {/* Model Metadata Card */}
      <div className="bg-slate-900/70 border border-slate-700/60 rounded p-2.5 flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5 text-fuchsia-300 font-semibold text-[11px]">
          <Cpu className="w-3.5 h-3.5 text-fuchsia-400" />
          <span>Active ML Model</span>
        </div>
        <div className="flex justify-between text-[11px] font-mono">
          <span className="text-gray-400">Model:</span>
          <span className="text-slate-200 font-bold">crater_detector_v1</span>
        </div>
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-gray-400">Version:</span>
          <span className="text-slate-300">1.0.0 (signed)</span>
        </div>
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-gray-400">Runtime:</span>
          <span className="text-slate-300">ONNX CPU (IR-10)</span>
        </div>
      </div>

      {/* Advisory Callout */}
      <div className="bg-amber-950/30 border border-amber-500/40 rounded p-2 flex items-start gap-1.5 text-[10px] text-amber-200">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
        <span>
          <strong>Advisory Note:</strong> ML crater detections are advisory. Always consult terrain slope hazards independently.
        </span>
      </div>

      {/* ML Confidence Threshold Slider */}
      <div className="flex flex-col gap-1.5 border-t border-white/10 pt-3">
        <div className="flex justify-between items-center text-[11px] text-gray-300">
          <label htmlFor="ml-confidence-range">ML Confidence Cutoff</label>
          <span className="font-mono text-fuchsia-300">{Math.round(layers.mlConfidenceThreshold * 100)}%</span>
        </div>
        <input
          id="ml-confidence-range"
          type="range"
          min="0.40"
          max="0.95"
          step="0.05"
          value={layers.mlConfidenceThreshold}
          onChange={(e) => onChange({ ...layers, mlConfidenceThreshold: Number(e.target.value) })}
          className="w-full accent-fuchsia-400 cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-gray-500 font-mono">
          <span>40% (Loose)</span>
          <span>60% (Default)</span>
          <span>95% (Strict)</span>
        </div>
      </div>

      {/* Colormap Selector */}
      <div className="flex flex-col gap-1.5 border-t border-white/10 pt-3">
        <div className="flex items-center gap-1.5 text-gray-300 font-medium text-[11px]">
          <Sliders className="w-3.5 h-3.5 text-gray-400" aria-hidden="true" />
          <label htmlFor="colormap-select">Slope Colormap</label>
        </div>
        <select
          id="colormap-select"
          value={layers.colormap}
          onChange={(e) => onChange({ ...layers, colormap: e.target.value as Colormap })}
          className="bg-gray-900 border border-white/10 rounded px-2.5 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-cyan-400"
        >
          <option value="viridis">Viridis (Perceptually Uniform)</option>
          <option value="magma">Magma (High Contrast)</option>
          <option value="terrain">Lunar Terrain Ramp</option>
        </select>
      </div>

      {/* Threshold Slider */}
      <div className="flex flex-col gap-1.5 border-t border-white/10 pt-3">
        <div className="flex justify-between items-center text-[11px] text-gray-300">
          <label htmlFor="slope-limit-range">Max Traversable Slope</label>
          <span className="font-mono text-cyan-300">{layers.maxSlopeLimit}&deg;</span>
        </div>
        <input
          id="slope-limit-range"
          type="range"
          min="5"
          max="35"
          step="1"
          value={layers.maxSlopeLimit}
          onChange={(e) => onChange({ ...layers, maxSlopeLimit: Number(e.target.value) })}
          className="w-full accent-cyan-400 cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-gray-500 font-mono">
          <span>5&deg; (Cautious)</span>
          <span>15&deg; (Nominal)</span>
          <span>35&deg; (Steep)</span>
        </div>
      </div>
    </aside>
  );
};
