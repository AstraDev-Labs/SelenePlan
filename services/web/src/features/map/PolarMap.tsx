import React, { useRef, useEffect, useState, useCallback } from "react";
import { ZoomIn, ZoomOut, RotateCcw, MapPin } from "lucide-react";
import { LayerState } from "./LayerControl";
import { PointInspection } from "./InspectorPanel";

interface PolarMapProps {
  layers: LayerState;
  onInspect: (inspection: PointInspection | null) => void;
}

// Colormap interpolators
function getViridisColor(t: number): [number, number, number] {
  // t in [0, 1]
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
      return 26.0 + 8.0 * Math.sin(dist / 300.0);
    }
    // Outer flanks
    return Math.max(2.0, 18.0 * Math.exp(-(dist - rimRadius) / 1200.0));
  }, []);

  // Render canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    // Save initial state
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
        const isHazard = slope > layers.maxSlopeLimit;

        let r = 25, g = 30, b = 45;

        if (layers.showSlope) {
          const normSlope = Math.min(1.0, slope / 45.0);
          const [cr, cg, cb] = layers.colormap === "magma" ? getMagmaColor(normSlope) : getViridisColor(normSlope);
          r = cr;
          g = cg;
          b = cb;
        } else if (layers.showHillshade) {
          // Low-angle polar sun from East (+x)
          const shade = Math.max(0.1, Math.min(1.0, 0.5 + 0.5 * (-xM / (Math.abs(xM) + 500))));
          r = Math.round(elev < -2000 ? 15 : 120 * shade);
          g = Math.round(elev < -2000 ? 20 : 130 * shade);
          b = Math.round(elev < -2000 ? 35 : 150 * shade);
        }

        if (layers.showHazard && isHazard) {
          r = Math.min(255, r + 160);
          g = Math.round(g * 0.3);
          b = Math.round(b * 0.3);
        }

        // Fill 2x2 block for crisp performance
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

    const rings = [1000, 2000, 3000, 4000]; // Metres
    rings.forEach((rM) => {
      const rPx = rM / scale;
      ctx.beginPath();
      ctx.arc(width / 2, height / 2, rPx, 0, Math.PI * 2);
      ctx.stroke();
    });

    // Crosshairs & Meridian Axes
    ctx.beginPath();
    ctx.moveTo(width / 2, 0);
    ctx.lineTo(width / 2, height);
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Shackleton Crater Label
    ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
    ctx.font = "11px 'Space Grotesk', sans-serif";
    ctx.fillText("Shackleton Crater Rim", width / 2 + 10, height / 2 - 85);
    ctx.fillText("South Pole (90°S)", width / 2 + 6, height / 2 + 15);

    ctx.restore();
  }, [zoom, pan, layers, getSlopeAt, getElevationAt]);

  // Mouse interaction for point inspection
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

    // Coordinate inverse projection
    const scale = (EXTENT_M * 2) / canvas.width / zoom;
    const xM = (px - (canvas.width / 2 + pan.x)) * scale;
    const yM = ((canvas.height / 2 + pan.y) - py) * scale;

    const slope = getSlopeAt(xM, yM);
    const elev = getElevationAt(xM, yM);
    const distM = Math.sqrt(xM * xM + yM * yM);
    const lat = 90.0 - (distM / 30300.0); // Approx polar arc
    const lon = (Math.atan2(xM, -yM) * 180.0) / Math.PI;

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
      feature_name: distM < 2100 ? "Shackleton Rim" : "Connecting Ridge",
    });
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true);
    const rect = e.currentTarget.getBoundingClientRect();
    setDragStart({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  return (
    <div className="relative w-full h-[620px] rounded-xl overflow-hidden border border-white/10 bg-black shadow-2xl">
      <canvas
        ref={canvasRef}
        width={700}
        height={620}
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
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
  );
};
