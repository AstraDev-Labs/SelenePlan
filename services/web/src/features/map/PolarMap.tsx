import React, { useCallback, useEffect, useRef, useState } from "react";
import { MapPin, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { LayerState } from "./LayerControl";
import { PointInspection } from "./InspectorPanel";
import { TimelineScrubber } from "./TimelineScrubber";

interface PolarMapProps {
  layers: LayerState;
  onInspect: (data: PointInspection | null) => void;
}

// Colormap ramps
function getViridisColor(t: number): [number, number, number] {
  const clamped = Math.max(0, Math.min(1, t));
  const r = Math.round(68 + clamped * (253 - 68));
  const g = Math.round(1 + clamped * (231 - 1));
  const b = Math.round(84 + clamped * (37 - 84));
  return [r, g, b];
}

function getMagmaColor(t: number): [number, number, number] {
  const clamped = Math.max(0, Math.min(1, t));
  const r = Math.round(20 + clamped * (251 - 20));
  const g = Math.round(11 + clamped * (252 - 11));
  const b = Math.round(54 + clamped * (191 - 54));
  return [r, g, b];
}

export const PolarMap: React.FC<PolarMapProps> = ({ layers, onInspect }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Timeline State (72 steps = 72 hours simulation of Shackleton South Pole AOI)
  const TOTAL_STEPS = 72;
  const [currentStep, setCurrentStep] = useState<number>(12);

  // Precomputed ISO timestamps for timeline
  const timestamps = useRef<string[]>(
    Array.from({ length: TOTAL_STEPS }, (_, i) => {
      const d = new Date(Date.UTC(2026, 2, 1, i, 0, 0));
      return d.toISOString().replace(".000Z", "Z");
    })
  ).current;

  // Map spatial parameters: 500x500 grid, 20m resolution, origin = -5000m to +5000m
  const GRID_SIZE = 500;
  const RESOLUTION_M = 20.0;
  const EXTENT_M = (GRID_SIZE * RESOLUTION_M) / 2; // 5000m

  // Compute synthetic terrain profile matching Shackleton Crater
  const getElevationAt = useCallback((xM: number, yM: number) => {
    const dist = Math.sqrt(xM * xM + yM * yM);
    const rimRadius = 2100.0; // 2.1 km radius
    if (dist < rimRadius) {
      // Parabolic bowl crater
      const depth = 4200.0;
      return -4200.0 + (depth * Math.pow(dist / rimRadius, 2));
    } else {
      // Ejecta blanket decay
      return -800.0 + (1200.0 * Math.pow(rimRadius / dist, 3));
    }
  }, []);

  const getSlopeAt = useCallback((xM: number, yM: number) => {
    const dist = Math.sqrt(xM * xM + yM * yM);
    const rimRadius = 2100.0;
    if (dist < 400.0) return 3.2; // Crater floor is relatively flat
    if (dist <= rimRadius) {
      // Steep walls
      return 15.0 + 17.0 * (dist / rimRadius);
    } else {
      return Math.max(2.0, 14.0 * Math.exp(-(dist - rimRadius) / 1500.0));
    }
  }, []);

  // Solar position at given step
  const getSunGeometryAt = useCallback((step: number) => {
    const az = (step * 5.0) % 360.0;
    const el = 1.54 * Math.sin((step / TOTAL_STEPS) * 2 * Math.PI + 0.2);
    return { az, el };
  }, [TOTAL_STEPS]);

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
    // Crater floor (dist < 1850m) is occulted by the surrounding 4 km high rim
    if (dist < 1850.0) return false;
    // Rim and connecting ridge have clear visibility to Earth (+2.4 deg elevation)
    return true;
  }, []);

  const { az: currentSunAz, el: currentSunEl } = getSunGeometryAt(currentStep);

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
        const isHazard = slope > layers.maxSlopeLimit;
        const lit = isPointLit(xM, yM, currentStep);
        const earthVis = isPointEarthVisible(xM, yM);
        const isPSR = distM < 1850.0;

        let r = 25, g = 30, b = 45;

        if (layers.showEarthVisibility) {
          if (earthVis) {
            // Direct to Earth line-of-sight: vibrant cyan
            r = 6; g = 182; b = 212;
          } else {
            // Communications blackout: deep dark crimson
            r = 75; g = 12; b = 30;
          }
        } else if (layers.showIllumination) {
          if (lit) {
            // Sunlit warm gold
            r = 230; g = 190; b = 80;
          } else {
            // Shadowed deep obsidian blue
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

        // Rover Hazard Overlay
        if (layers.showHazard && isHazard) {
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

    // Annotations
    ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
    ctx.font = "11px 'Space Grotesk', sans-serif";
    ctx.fillText("Shackleton Crater Rim", width / 2 + 10, height / 2 - 85);
    ctx.fillText("South Pole (90°S)", width / 2 + 6, height / 2 + 15);

    ctx.restore();
  }, [zoom, pan, layers, currentStep, getSlopeAt, getElevationAt, isPointLit, isPointEarthVisible]);

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
      is_hazard: slope > layers.maxSlopeLimit,
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
            onClick={() => setZoom((z) => Math.max(0.5, z * 0.8))}
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

        {/* Projection Scale Indicator */}
        <div className="absolute bottom-3 left-4 flex items-center gap-2 bg-gray-950/80 px-2.5 py-1 rounded border border-white/10 text-[10px] font-mono text-cyan-300">
          <MapPin className="w-3 h-3 text-cyan-400" />
          <span>Scale: 20 m/pixel | CRS: IAU_2015:30100 (Polar Stereographic)</span>
        </div>
      </div>

      {/* Embedded Timeline Scrubber */}
      <TimelineScrubber
        totalSteps={TOTAL_STEPS}
        currentStep={currentStep}
        onStepChange={setCurrentStep}
        timestamps={timestamps}
        litFraction={0.62}
        sunAzimuthDeg={currentSunAz}
        sunElevationDeg={currentSunEl}
      />
    </div>
  );
};
