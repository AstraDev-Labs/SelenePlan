import React, { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, FastForward, Pause, Play, RotateCcw, Sun } from "lucide-react";

export interface TimelineScrubberProps {
  totalSteps: number;
  currentStep: number;
  onStepChange: (step: number) => void;
  timestamps: string[];
  litFraction?: number;
  sunAzimuthDeg?: number;
  sunElevationDeg?: number;
  isLoading?: boolean;
}

export const TimelineScrubber: React.FC<TimelineScrubberProps> = ({
  totalSteps,
  currentStep,
  onStepChange,
  timestamps,
  litFraction = 0.5,
  sunAzimuthDeg = 0.0,
  sunElevationDeg = 0.5,
  isLoading = false,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(1);
  const playTimerRef = useRef<number | null>(null);
  const currentStepRef = useRef<number>(currentStep);

  useEffect(() => {
    currentStepRef.current = currentStep;
  }, [currentStep]);

  // Play / Pause loop
  useEffect(() => {
    if (isPlaying && totalSteps > 0) {
      const intervalMs = Math.max(100, 1000 / speedMultiplier);
      playTimerRef.current = window.setInterval(() => {
        const next = currentStepRef.current + 1;
        onStepChange(next < totalSteps ? next : 0);
      }, intervalMs);
    } else if (playTimerRef.current !== null) {
      clearInterval(playTimerRef.current);
      playTimerRef.current = null;
    }

    return () => {
      if (playTimerRef.current !== null) {
        clearInterval(playTimerRef.current);
      }
    };
  }, [isPlaying, speedMultiplier, totalSteps, onStepChange]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowRight") {
      onStepChange(Math.min(totalSteps - 1, currentStep + 1));
    } else if (e.key === "ArrowLeft") {
      onStepChange(Math.max(0, currentStep - 1));
    } else if (e.key === "Home") {
      onStepChange(0);
    } else if (e.key === "End") {
      onStepChange(totalSteps - 1);
    } else if (e.key === " ") {
      e.preventDefault();
      setIsPlaying(!isPlaying);
    }
  };

  const currentIso = timestamps[currentStep] || "2026-03-01T00:00:00Z";

  return (
    <div
      aria-label="Illumination Timeline Player"
      className="glass-panel p-3 px-4 flex flex-col gap-2.5 w-full max-w-4xl border border-cyan-500/20 shadow-2xl backdrop-blur-md"
    >
      {/* Header telemetry info */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-amber-400 font-semibold tracking-wide">
            <Sun className={`w-4 h-4 ${isPlaying ? "animate-spin" : ""}`} aria-hidden="true" />
            <span>SOLAR TIMELINE</span>
          </div>
          <span className="font-mono bg-black/40 px-2.5 py-0.5 rounded text-cyan-200 border border-cyan-900/40 text-[11px]">
            {currentIso}
          </span>
          {isLoading && (
            <span className="badge badge-amber text-[10px] animate-pulse">
              SYNCING SLICE...
            </span>
          )}
        </div>

        <div className="flex items-center gap-4 text-[11px] font-mono text-gray-300">
          <div>
            <span className="text-gray-400">Step: </span>
            <span className="text-cyan-300 font-bold">{currentStep + 1}</span> / {totalSteps}
          </div>
          <div>
            <span className="text-gray-400">Sun El: </span>
            <span className={sunElevationDeg >= 0 ? "text-amber-300" : "text-indigo-400"}>
              {sunElevationDeg >= 0 ? "+" : ""}{sunElevationDeg.toFixed(2)}&deg;
            </span>
          </div>
          <div>
            <span className="text-gray-400">Sun Az: </span>
            <span className="text-cyan-300">{sunAzimuthDeg.toFixed(1)}&deg;</span>
          </div>
          <div>
            <span className="text-gray-400">Lit Fraction: </span>
            <span className="text-emerald-300 font-semibold">{(litFraction * 100).toFixed(1)}%</span>
          </div>
        </div>
      </div>

      {/* Scrubber slider */}
      <div className="flex items-center gap-3">
        <span className="text-[10px] font-mono text-gray-400">T0</span>
        <input
          type="range"
          id="timeline-scrubber-slider"
          aria-label="Timeline Scrubber Slider"
          min={0}
          max={Math.max(0, totalSteps - 1)}
          value={currentStep}
          onChange={(e) => onStepChange(parseInt(e.target.value, 10))}
          onKeyDown={handleKeyDown}
          className="w-full h-1.5 bg-gray-700/60 rounded-lg appearance-none cursor-pointer accent-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/50"
        />
        <span className="text-[10px] font-mono text-gray-400">T{totalSteps - 1}</span>
      </div>

      {/* Playback controls */}
      <div className="flex items-center justify-between pt-1 border-t border-white/5">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => onStepChange(Math.max(0, currentStep - 1))}
            aria-label="Previous Time Step"
            className="p-1.5 rounded hover:bg-white/10 text-gray-300 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsPlaying(!isPlaying)}
            aria-label={isPlaying ? "Pause Timeline Playback" : "Play Timeline Playback"}
            className="flex items-center gap-1 px-3 py-1 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-500/40 rounded transition-colors text-xs font-semibold"
          >
            {isPlaying ? (
              <>
                <Pause className="w-3.5 h-3.5" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                <span>Play</span>
              </>
            )}
          </button>

          <button
            onClick={() => onStepChange(Math.min(totalSteps - 1, currentStep + 1))}
            aria-label="Next Time Step"
            className="p-1.5 rounded hover:bg-white/10 text-gray-300 transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>

          <button
            onClick={() => {
              setIsPlaying(false);
              onStepChange(0);
            }}
            aria-label="Reset to Timeline Start"
            className="p-1.5 rounded hover:bg-white/10 text-gray-400 hover:text-gray-200 transition-colors ml-1"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Speed multiplier selector */}
        <div className="flex items-center gap-1 text-[11px] font-sans">
          <FastForward className="w-3.5 h-3.5 text-gray-400 mr-1" aria-hidden="true" />
          <span className="text-gray-400 mr-1">Speed:</span>
          {[1, 2, 5, 10].map((rate) => (
            <button
              key={rate}
              onClick={() => setSpeedMultiplier(rate)}
              aria-label={`Set playback speed ${rate}x`}
              className={`px-1.5 py-0.5 rounded text-[10px] font-mono transition-colors ${
                speedMultiplier === rate
                  ? "bg-cyan-500/30 text-cyan-200 font-bold border border-cyan-400/40"
                  : "bg-white/5 text-gray-400 hover:bg-white/10"
              }`}
            >
              {rate}x
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
