import React, { useRef, useEffect, useState, useCallback } from "react";
import { LayerState } from "./LayerControl";
import { PointInspection } from "./InspectorPanel";
import { ZoomIn, ZoomOut, RotateCcw } from "lucide-react";

interface PolarMapProps {
  layers: LayerState;
  onInspect: (data: PointInspection | null) => void;
  currentStep?: number;
}

// 20 km x 20 km Shackleton AOI extent
const EXTENT_M = 10000.0;
const TOTAL_STEPS = 708;

// Simulated ML Detected Craters (advisory obstacles in Shackleton perimeter)
const SIMULATED_ML_CRATERS = [
  { x: 1400, y: 1600, r: 280, conf: 0.88, name: "Crater A (ML Advisory)" },
  { x: -1800, y: 800, r: 220, conf: 0.82, name: "Crater B (ML Advisory)" },
  { x: 500, y: -2200, r: 310, conf: 0.79, name: "Crater C (ML Advisory)" },
  { x: -1200, y: -1900, r: 190, conf: 0.84, name: "Crater D (ML Advisory)" },
];

export const PolarMap: React.FC<PolarMapProps> = ({
  layers,
  onInspect,
  currentStep = 0,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Analytic Shackleton DEM profile generator
  const getElevationAt = useCallback((xM: number, yM: number) => {
    const dist = Math.sqrt(xM * xM + yM * yM);
    const rimRadius = 2100.0;
    const depth = 4200.0;
    if (dist <= rimRadius) {
      return -4200.0 + (depth * Math.pow(dist / rimRadius, 2));
    } else {
      return -800.0 + (1200.0 * Math.pow(rimRadius / dist, 3));
    }
  }, []);

  const getSlopeAt = useCallback((xM: number, yM: number) => {
    const dist = Math.sqrt(xM * xM + yM * yM);
    const rimRadius = 2100.0;
    if (dist < 400.0) return 3.2;
    if (dist <= rimRadius) {
      return 15.0 + 17.0 * (dist / rimRadius);
    } else {
      return Math.max(2.0, 14.0 * Math.exp(-(dist - rimRadius) / 1500.0));
    }
  }, []);

  const getMLHazardAt = useCallback((xM: number, yM: number) => {
    for (const c of SIMULATED_ML_CRATERS) {
      const d = Math.hypot(xM - c.x, yM - c.y);
      if (d <= c.r) {
        return { detected: true, confidence: c.conf * (1.0 - 0.2 * (d / c.r)) };
      }
    }
    return { detected: false, confidence: 0.0 };
  }, []);

  // Solar position at given step
  const getSunGeometryAt = useCallback((step: number) => {
    const az = (step * 5.0) % 360.0;
    const el = 1.54 * Math.sin((step / TOTAL_STEPS) * 2 * Math.PI + 0.2);
    return { az, el };
  }, []);

  // Point illumination evaluation
  const isPointLit = useCallback((xM: number, yM: number, step: number) => {
    const dist = Math.sqrt(xM * xM + yM * yM);
    const { el } = getSunGeometryAt(step);
    if (dist < 1850.0) return false;
    if (dist >= 1950.0 && dist <= 2300.0) {
      return el > -0.2;
    }
    return el > 0.4;
  }, [getSunGeometryAt]);

  // Point Earth direct-to-Earth line of sight
  const isPointEarthVisible = useCallback((xM: number, yM: number) => {
    const dist = Math.sqrt(xM * xM + yM * yM);
    if (dist < 1850.0) return false;
    return true;
  }, []);

  // Render Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.translate(width / 2 + pan.x, height / 2 + pan.y);
    ctx.scale(zoom, zoom);

    // Draw base map raster
    const imgData = ctx.createImageData(width, height);
    const data = imgData.data;
    const scale = (EXTENT_M * 2) / width;

    for (let py = 0; py < height; py += 2) {
      const yM = (height / 2 - py) * scale;
      for (let px = 0; px < width; px += 2) {
        const xM = (px - width / 2) * scale;
        const slope = getSlopeAt(xM, yM);
        const elev = getElevationAt(xM, yM);
        const distM = Math.sqrt(xM * xM + yM * yM);
        const isTerrainHazard = slope > layers.maxSlopeLimit;
        const mlHazard = getMLHazardAt(xM, yM);
        const isMLHazard = mlHazard.detected && mlHazard.confidence >= layers.mlConfidenceThreshold;
        const isFusedHazard = isTerrainHazard || isMLHazard;

        const lit = isPointLit(xM, yM, currentStep);
        const earthVis = isPointEarthVisible(xM, yM);
        const isPSR = distM < 1850.0;

        let r = 25, g = 30, b = 45;

        if (layers.showFusedHazard && isFusedHazard) {
          // Fused Hazard: Vibrant Warning Amber / Crimson
          r = 225; g = 50; b = 40;
        } else if (layers.showMLHazard && isMLHazard) {
          // ML Crater Detection: Fuchsia / Magenta
          r = 217; g = 70; b = 239;
        } else if (layers.showEarthVisibility) {
          if (earthVis) {
            r = 6; g = 182; b = 212;
          } else {
            r = 75; g = 12; b = 30;
          }
        } else if (layers.showIllumination) {
          if (lit) {
            r = 230; g = 190; b = 80;
          } else {
            r = 15; g = 20; b = 35;
          }
        } else if (layers.showSlope) {
          const normSlope = Math.min(1.0, slope / 45.0);
          const [cr, cg, cb] = layers.colormap === "magma" ? getMagmaColor(normSlope) : getViridisColor(normSlope);
          r = cr;
          g = cg;
          b = cb;
        } else if (layers.showHillshade) {
          const shade = Math.max(0.1, Math.min(1.0, 0.5 + 0.5 * (-xM / (Math.abs(xM) + 500))));
          r = Math.round(elev < -2000 ? 15 : 120 * shade);
          g = Math.round(elev < -2000 ? 20 : 130 * shade);
          b = Math.round(elev < -2000 ? 35 : 150 * shade);
        }

        // PSR Overlay
        if (layers.showPSR && isPSR) {
          r = Math.round(r * 0.4 + 90);
          g = Math.round(g * 0.3 + 40);
          b = Math.round(b * 0.4 + 200);
        }

        // Rover Terrain Slope Hazard Overlay (when fused is not already showing)
        if (layers.showHazard && !layers.showFusedHazard && isTerrainHazard) {
          r = Math.min(255, r + 150);
          g = Math.round(g * 0.3);
          b = Math.round(b * 0.3);
        }

        // 2x2 block fill
        for (let dy = 0; dy < 2; dy++) {
          for (let dx = 0; dx < 2; dx++) {
            const idx = ((py + dy) * width + (px + dx)) * 4;
            data[idx] = r;
            data[idx + 1] = g;
            data[idx + 2] = b;
            data[idx + 3] = 255;
          }
        }
      }
    }

    ctx.putImageData(imgData, 0, 0);

    // Overlay Polar Coordinate Grid Rings
    ctx.strokeStyle = "rgba(56, 189, 248, 0.25)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);

    const rings = [1000, 2000, 3000, 4000];
    rings.forEach((rM) => {
      const rPx = rM / scale;
      ctx.beginPath();
      ctx.arc(width / 2, height / 2, rPx, 0, Math.PI * 2);
      ctx.stroke();
    });

    // Crosshairs
    ctx.beginPath();
    ctx.moveTo(width / 2, 0);
    ctx.lineTo(width / 2, height);
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw Vector Crater Circles when ML Hazard Layer is active
    if (layers.showMLHazard || layers.showFusedHazard) {
      SIMULATED_ML_CRATERS.forEach((c) => {
        const px = width / 2 + (c.x / scale);
        const py = height / 2 - (c.y / scale);
        const rPx = c.r / scale;

        ctx.strokeStyle = "rgba(217, 70, 239, 0.85)";
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 3]);
        ctx.beginPath();
        ctx.arc(px, py, rPx, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label
        ctx.fillStyle = "rgba(240, 171, 252, 0.95)";
        ctx.font = "9px 'Space Grotesk', monospace";
        ctx.fillText(`${c.name} (${Math.round(c.conf * 100)}%)`, px - rPx, py - rPx - 4);
      });
    }

    // Annotations
    ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
    ctx.font = "11px 'Space Grotesk', sans-serif";
    ctx.fillText("Shackleton Crater Rim", width / 2 + 10, height / 2 - 85);
    ctx.fillText("South Pole (90°S)", width / 2 + 6, height / 2 + 15);

    ctx.restore();
  }, [zoom, pan, layers, currentStep, getSlopeAt, getElevationAt, getMLHazardAt, isPointLit, isPointEarthVisible]);

  // Mouse move point inspector
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;

    if (isDragging) {
      setPan({
        x: pan.x + (px - dragStart.x),
        y: pan.y + (py - dragStart.y),
      });
      setDragStart({ x: px, y: py });
      return;
    }

    const scale = (EXTENT_M * 2) / canvas.width / zoom;
    const xM = (px - (canvas.width / 2 + pan.x)) * scale;
    const yM = ((canvas.height / 2 + pan.y) - py) * scale;

    const slope = getSlopeAt(xM, yM);
    const elev = getElevationAt(xM, yM);
    const distM = Math.sqrt(xM * xM + yM * yM);
    const lat = 90.0 - (distM / 30300.0);
    const lon = (Math.atan2(xM, -yM) * 180.0) / Math.PI;
    const lit = isPointLit(xM, yM, currentStep);
    const earthVis = isPointEarthVisible(xM, yM);
    const isPSR = distM < 1850.0;
    const mlHazard = getMLHazardAt(xM, yM);
    const isTerrainHazard = slope > layers.maxSlopeLimit;
    const isMLHazard = mlHazard.detected && mlHazard.confidence >= layers.mlConfidenceThreshold;
    const isFusedHazard = isTerrainHazard || isMLHazard;

    // Build 48h solar & earth series
    const sunSeries = Array.from({ length: 48 }, (_, t) => isPointLit(xM, yM, t));
    const earthSeries = Array.from({ length: 48 }, () => earthVis);
    const litCount = sunSeries.filter(Boolean).length;
    const litFrac = isPSR ? 0.0 : litCount / sunSeries.length;

    onInspect({
      x_m: xM,
      y_m: yM,
      lat_deg: lat,
      lon_deg: lon >= 0 ? lon : lon + 360,
      elevation_m: elev,
      slope_deg: slope,
      aspect_deg: (Math.atan2(xM, yM) * 180.0) / Math.PI,
      roughness_m: slope * 0.08,
      is_hazard: isTerrainHazard,
      feature_name: distM < 2100 ? (isPSR ? "Shackleton PSR Floor" : "Shackleton Rim") : "Connecting Ridge",
      is_lit: lit,
      lit_fraction: litFrac,
      longest_dark_hours: isPSR ? 708.0 : (1.0 - litFrac) * 48.0,
      is_psr: isPSR,
      time_series: sunSeries,
      earth_visible: earthVis,
      earth_elevation_deg: 2.37,
      earth_visible_fraction: isPSR ? 0.0 : 0.88,
      longest_blackout_hours: isPSR ? 708.0 : 12.0,
      earth_series: earthSeries,
      ml_hazard_detected: mlHazard.detected,
      ml_confidence: mlHazard.confidence,
      fused_hazard: isFusedHazard,
    });
  };

  return (
    <div className="flex flex-col gap-3 w-full">
      <div className="relative w-full h-[580px] rounded-xl overflow-hidden border border-white/10 bg-black shadow-2xl">
        <canvas
          ref={canvasRef}
          width={700}
          height={580}
          onMouseMove={handleMouseMove}
          onMouseDown={(e) => {
            setIsDragging(true);
            const rect = e.currentTarget.getBoundingClientRect();
            setDragStart({ x: e.clientX - rect.left, y: e.clientY - rect.top });
          }}
          onMouseUp={() => setIsDragging(false)}
          onMouseLeave={() => { setIsDragging(false); onInspect(null); }}
          className="w-full h-full cursor-crosshair block"
          aria-label="2D Lunar South Pole Polar Map"
        />

        {/* Map Control Buttons */}
        <div className="absolute top-4 right-4 flex flex-col gap-1.5 glass-panel p-1.5">
          <button
            onClick={() => setZoom((z) => Math.min(3.0, z * 1.25))}
            aria-label="Zoom In"
            title="Zoom In"
            className="p-1.5 rounded hover:bg-white/10 text-gray-300 hover:text-cyan-300 transition-colors"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoom((z) => Math.max(0.5, z / 1.25))}
            aria-label="Zoom Out"
            title="Zoom Out"
            className="p-1.5 rounded hover:bg-white/10 text-gray-300 hover:text-cyan-300 transition-colors"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={() => { setZoom(1.0); setPan({ x: 0, y: 0 }); }}
            aria-label="Reset View"
            title="Reset View"
            className="p-1.5 rounded hover:bg-white/10 text-gray-300 hover:text-cyan-300 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

// Helper colormap interpolators
function getViridisColor(t: number): [number, number, number] {
  const r = Math.round(68 + t * (253 - 68));
  const g = Math.round(1 + t * (231 - 1));
  const b = Math.round(84 + t * (37 - 84));
  return [r, g, b];
}

function getMagmaColor(t: number): [number, number, number] {
  const r = Math.round(0 + t * (251 - 0));
  const g = Math.round(0 + t * (136 - 0));
  const b = Math.round(4 + t * (153 - 4));
  return [r, g, b];
}
