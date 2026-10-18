import React, { useRef, useEffect, useState, useCallback } from "react";
import { LayerState } from "./LayerControl";
import { PointInspection } from "./InspectorPanel";
import { ZoomIn, ZoomOut, RotateCcw, Navigation2, Compass, MapPin } from "lucide-react";

interface PolarMapProps {
  layers: LayerState;
  onInspect: (data: PointInspection | null) => void;
  currentStep?: number;
}

// 20 km x 20 km Shackleton AOI extent (+/- 10 km from South Pole)
const EXTENT_M = 10000.0;
const TOTAL_STEPS = 708;

// Simulated ML Detected Craters (advisory obstacles in Shackleton perimeter)
const SIMULATED_ML_CRATERS = [
  { x: 1400, y: 1600, r: 280, conf: 0.88, name: "Crater Alpha (ML 88%)" },
  { x: -1800, y: 800, r: 220, conf: 0.82, name: "Crater Beta (ML 82%)" },
  { x: 500, y: -2200, r: 310, conf: 0.79, name: "Crater Gamma (ML 79%)" },
  { x: -1200, y: -1900, r: 190, conf: 0.84, name: "Crater Delta (ML 84%)" },
];

// Planned Rover Traverse Waypoints
const MISSION_WAYPOINTS = [
  { id: "WP-0", label: "LANDER-ALPHA", x: -2600, y: -800, elev: -790, type: "start" },
  { id: "WP-1", label: "RIDGE-SPINE", x: -2100, y: 300, elev: -840, type: "waypoint" },
  { id: "WP-2", label: "SHACKLETON-CREST", x: -1500, y: 1400, elev: -910, type: "science" },
  { id: "WP-3", label: "PSR-EDGE", x: -600, y: 1750, elev: -1600, type: "target" },
];

export const PolarMap: React.FC<PolarMapProps> = ({
  layers,
  onInspect,
  currentStep = 0,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const offscreenCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [cursorHud, setCursorHud] = useState<{ xM: number; yM: number; elev: number; slope: number; lat: number; lon: number } | null>(null);
  const [dashOffset, setDashOffset] = useState<number>(0);

  // Animate traverse dashed route
  useEffect(() => {
    const timer = setInterval(() => {
      setDashOffset((prev) => (prev + 1) % 16);
    }, 90);
    return () => clearInterval(timer);
  }, []);

  // Analytic High-Fidelity Shackleton DEM profile generator
  const getElevationAt = useCallback((xM: number, yM: number) => {
    const dist = Math.sqrt(xM * xM + yM * yM);
    const rimRadius = 2100.0;
    const depth = 4200.0;

    // Connecting Ridge Spine elevation boost along the ridge
    const ridgeDist = Math.hypot(xM - (-2200), yM - 0);
    const ridgeBoost = 350.0 * Math.exp(-Math.pow(ridgeDist / 1400.0, 2));

    // Secondary micro-craters
    let craterDent = 0;
    for (const c of SIMULATED_ML_CRATERS) {
      const d = Math.hypot(xM - c.x, yM - c.y);
      if (d < c.r * 1.5) {
        craterDent += 180.0 * Math.pow(Math.max(0, 1 - d / c.r), 2);
      }
    }

    if (dist <= rimRadius) {
      return -4200.0 + (depth * Math.pow(dist / rimRadius, 2)) - craterDent;
    } else {
      const base = -800.0 + (1200.0 * Math.pow(rimRadius / dist, 3));
      return base + ridgeBoost - craterDent;
    }
  }, []);

  // Physically grounded slope based on numerical gradient
  const getSlopeAt = useCallback((xM: number, yM: number) => {
    const delta = 30.0;
    const zE = getElevationAt(xM + delta, yM);
    const zW = getElevationAt(xM - delta, yM);
    const zN = getElevationAt(xM, yM + delta);
    const zS = getElevationAt(xM, yM - delta);

    const dzdx = (zE - zW) / (2 * delta);
    const dzdy = (zN - zS) / (2 * delta);
    const grad = Math.sqrt(dzdx * dzdx + dzdy * dzdy);
    const slopeDeg = Math.atan(grad) * (180.0 / Math.PI);
    return Math.min(60.0, slopeDeg);
  }, [getElevationAt]);

  const getMLHazardAt = useCallback((xM: number, yM: number) => {
    for (const c of SIMULATED_ML_CRATERS) {
      const d = Math.hypot(xM - c.x, yM - c.y);
      if (d <= c.r) {
        return { detected: true, confidence: c.conf * (1.0 - 0.2 * (d / c.r)), name: c.name };
      }
    }
    return { detected: false, confidence: 0.0, name: "" };
  }, []);

  const getSunGeometryAt = useCallback((step: number) => {
    const az = (step * 5.0) % 360.0;
    const el = 1.8 * Math.sin((step / TOTAL_STEPS) * 2 * Math.PI + 0.3) + 1.2;
    return { az, el };
  }, []);

  const isPointLit = useCallback((xM: number, yM: number, step: number) => {
    const dist = Math.sqrt(xM * xM + yM * yM);
    const { el } = getSunGeometryAt(step);
    if (dist < 1850.0) return false;
    if (dist >= 1950.0 && dist <= 2350.0) {
      return el > -0.2;
    }
    return el > 0.4;
  }, [getSunGeometryAt]);

  const isPointEarthVisible = useCallback((xM: number, yM: number) => {
    const dist = Math.sqrt(xM * xM + yM * yM);
    if (dist < 1850.0) return false;
    return true;
  }, []);

  // Main Canvas Render
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Initialize or resize offscreen canvas
    if (!offscreenCanvasRef.current) {
      offscreenCanvasRef.current = document.createElement("canvas");
    }
    const offCanvas = offscreenCanvasRef.current;
    if (offCanvas.width !== width || offCanvas.height !== height) {
      offCanvas.width = width;
      offCanvas.height = height;
    }
    const offCtx = offCanvas.getContext("2d");
    if (!offCtx) return;

    // Clear canvases
    ctx.clearRect(0, 0, width, height);
    offCtx.clearRect(0, 0, width, height);

    const scale = (EXTENT_M * 2) / width;
    const imgData = offCtx.createImageData(width, height);
    const data = imgData.data;

    // Sun vector for hillshade
    const sunGeom = getSunGeometryAt(currentStep);
    const sunAzRad = (sunGeom.az * Math.PI) / 180.0;
    const sunElRad = (Math.max(1.0, sunGeom.el) * Math.PI) / 180.0;
    const sunX = Math.cos(sunElRad) * Math.sin(sunAzRad);
    const sunY = -Math.cos(sunElRad) * Math.cos(sunAzRad);
    const sunZ = Math.sin(sunElRad);

    // Compute Raster Terrain on Offscreen Canvas
    for (let py = 0; py < height; py += 2) {
      const yM = (height / 2 - py) * scale;
      for (let px = 0; px < width; px += 2) {
        const xM = (px - width / 2) * scale;

        const elev = getElevationAt(xM, yM);
        const slope = getSlopeAt(xM, yM);
        const distM = Math.sqrt(xM * xM + yM * yM);

        const isTerrainHazard = slope > layers.maxSlopeLimit;
        const mlHazard = getMLHazardAt(xM, yM);
        const isMLHazard = mlHazard.detected && mlHazard.confidence >= layers.mlConfidenceThreshold;
        const isFusedHazard = isTerrainHazard || isMLHazard;

        const lit = isPointLit(xM, yM, currentStep);
        const earthVis = isPointEarthVisible(xM, yM);
        const isPSR = distM < 1850.0;

        // Hillshade
        const delta = 30.0;
        const dzdx = (getElevationAt(xM + delta, yM) - getElevationAt(xM - delta, yM)) / (2 * delta);
        const dzdy = (getElevationAt(xM, yM + delta) - getElevationAt(xM, yM - delta)) / (2 * delta);
        const len = Math.sqrt(dzdx * dzdx + dzdy * dzdy + 1.0);
        const nx = -dzdx / len;
        const ny = -dzdy / len;
        const nz = 1.0 / len;

        const dot = nx * sunX + ny * sunY + nz * sunZ;
        const directShade = Math.max(0.0, dot);
        const ambient = isPSR ? 0.03 : 0.15;
        const shade = Math.min(1.0, ambient + directShade * 0.85);

        // Base Lunar Regolith
        let r = Math.round(30 + shade * 130);
        let g = Math.round(35 + shade * 135);
        let b = Math.round(48 + shade * 150);

        if (elev > -850) {
          r = Math.min(255, r + 12);
          g = Math.min(255, g + 12);
          b = Math.min(255, b + 16);
        }

        if (isPSR) {
          r = Math.round(12 + shade * 20);
          g = Math.round(16 + shade * 25);
          b = Math.round(30 + shade * 40);
        }

        // Layer: Slope Map
        if (layers.showSlope) {
          const normSlope = Math.min(1.0, slope / 45.0);
          const [cr, cg, cb] = layers.colormap === "magma" ? getMagmaColor(normSlope) : getViridisColor(normSlope);
          const alpha = 0.65;
          r = Math.round(cr * alpha + r * (1 - alpha));
          g = Math.round(cg * alpha + g * (1 - alpha));
          b = Math.round(cb * alpha + b * (1 - alpha));
        }

        // Layer: Illumination
        if (layers.showIllumination) {
          if (lit) {
            r = Math.min(255, Math.round(r * 1.15 + 40));
            g = Math.min(255, Math.round(g * 1.12 + 30));
            b = Math.min(255, Math.round(b * 0.95));
          } else if (!layers.showSlope) {
            r = Math.round(r * 0.5);
            g = Math.round(r * 0.5);
            b = Math.round(b * 0.6);
          }
        }

        // Layer: Earth Line-of-Sight
        if (layers.showEarthVisibility) {
          if (earthVis) {
            r = Math.round(r * 0.8 + 15);
            g = Math.round(g * 0.8 + 45);
            b = Math.round(b * 0.8 + 80);
          } else {
            r = Math.min(255, Math.round(r * 0.6 + 90));
            g = Math.round(g * 0.4);
            b = Math.round(b * 0.4);
          }
        }

        // Layer: PSR
        if (layers.showPSR && isPSR) {
          r = Math.round(r * 0.35 + 25);
          g = Math.round(g * 0.35 + 45);
          b = Math.round(b * 0.35 + 140);
        }

        // Layer: Fused Hazard Overlay (semi-transparent crimson/amber)
        if (layers.showFusedHazard && isFusedHazard) {
          r = Math.min(255, Math.round(r * 0.45 + 155));
          g = Math.round(g * 0.4 + 40);
          b = Math.round(b * 0.4 + 30);
        } else if (layers.showHazard && isTerrainHazard) {
          r = Math.min(255, Math.round(r * 0.45 + 140));
          g = Math.round(g * 0.35 + 30);
          b = Math.round(b * 0.35 + 30);
        } else if (layers.showMLHazard && isMLHazard) {
          r = Math.min(255, Math.round(r * 0.45 + 130));
          g = Math.round(g * 0.35 + 25);
          b = Math.min(255, Math.round(b * 0.45 + 145));
        }

        // 2x2 block
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

    offCtx.putImageData(imgData, 0, 0);

    // ==========================================================
    // Render on Main Canvas with Transform Matrix (Zoom & Pan)
    // ==========================================================
    ctx.save();
    ctx.translate(width / 2 + pan.x, height / 2 + pan.y);
    ctx.scale(zoom, zoom);

    // Draw Raster Base centered at (0, 0)
    ctx.drawImage(offCanvas, -width / 2, -height / 2);

    // Polar Range Rings (Centered at 0, 0 - South Pole)
    ctx.strokeStyle = "rgba(56, 189, 248, 0.25)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 6]);

    const rings = [1000, 2000, 3000, 4000, 6000];
    rings.forEach((rM) => {
      const rPx = rM / scale;
      ctx.beginPath();
      ctx.arc(0, 0, rPx, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = "rgba(148, 163, 184, 0.7)";
      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.fillText(`${(rM / 1000).toFixed(0)} km`, rPx + 4, -4);
    });

    // Crosshairs through South Pole (0, 0)
    ctx.strokeStyle = "rgba(56, 189, 248, 0.35)";
    ctx.beginPath();
    ctx.moveTo(0, -height);
    ctx.lineTo(0, height);
    ctx.moveTo(-width, 0);
    ctx.lineTo(width, 0);
    ctx.stroke();
    ctx.setLineDash([]);

    // Vector Annotations for ML Craters
    if (layers.showMLHazard || layers.showFusedHazard) {
      SIMULATED_ML_CRATERS.forEach((c) => {
        const px = c.x / scale;
        const py = -c.y / scale;
        const rPx = c.r / scale;

        ctx.strokeStyle = "rgba(217, 70, 239, 0.9)";
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.arc(px, py, rPx, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
        ctx.strokeStyle = "rgba(217, 70, 239, 0.6)";
        ctx.lineWidth = 1;
        const text = `${c.name}`;
        ctx.font = "10px 'JetBrains Mono', monospace";
        const tw = ctx.measureText(text).width;
        ctx.fillRect(px - rPx, py - rPx - 18, tw + 8, 14);
        ctx.strokeRect(px - rPx, py - rPx - 18, tw + 8, 14);

        ctx.fillStyle = "#f5d0fe";
        ctx.fillText(text, px - rPx + 4, py - rPx - 7);
      });
    }

    // Traverse Route Vector
    ctx.save();
    ctx.strokeStyle = "rgba(14, 165, 233, 0.4)";
    ctx.lineWidth = 6;
    ctx.beginPath();
    MISSION_WAYPOINTS.forEach((wp, i) => {
      const px = wp.x / scale;
      const py = -wp.y / scale;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();

    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2.5;
    ctx.setLineDash([8, 6]);
    ctx.lineDashOffset = -dashOffset;
    ctx.stroke();
    ctx.setLineDash([]);

    // Waypoints
    MISSION_WAYPOINTS.forEach((wp) => {
      const px = wp.x / scale;
      const py = -wp.y / scale;

      ctx.fillStyle = wp.type === "start" ? "#10b981" : wp.type === "target" ? "#f59e0b" : "#38bdf8";
      ctx.beginPath();
      ctx.arc(px, py, wp.type === "start" ? 6 : 4.5, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(px, py, wp.type === "start" ? 8 : 6.5, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = "rgba(10, 15, 30, 0.9)";
      ctx.strokeStyle = "rgba(56, 189, 248, 0.5)";
      ctx.lineWidth = 1;
      ctx.font = "10px 'JetBrains Mono', monospace";
      const wLabel = `${wp.label} (${wp.elev}m)`;
      const lw = ctx.measureText(wLabel).width;
      ctx.fillRect(px + 10, py - 14, lw + 8, 16);
      ctx.strokeRect(px + 10, py - 14, lw + 8, 16);

      ctx.fillStyle = "#ffffff";
      ctx.fillText(wLabel, px + 14, py - 2);
    });
    ctx.restore();

    // Feature Labels
    ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
    ctx.font = "bold 12px 'Space Grotesk', sans-serif";
    ctx.shadowColor = "rgba(0, 0, 0, 0.8)";
    ctx.shadowBlur = 6;
    ctx.fillText("Shackleton Crater (Rim)", 15, -85);
    ctx.fillText("South Pole (90.00°S)", 8, 18);

    ctx.fillStyle = "rgba(148, 163, 184, 0.85)";
    ctx.font = "10px 'Space Grotesk', sans-serif";
    ctx.fillText("Connecting Ridge", -230, 90);
    ctx.fillText("PSR Basin (-4,200m)", -100, -10);
    ctx.shadowBlur = 0;

    // Sun Vector Indicator
    const arrowLen = 45;
    const arrowStartX = width / 2 - 80;
    const arrowStartY = -height / 2 + 70;
    const arrowEndX = arrowStartX - Math.sin(sunAzRad) * arrowLen;
    const arrowEndY = arrowStartY + Math.cos(sunAzRad) * arrowLen;

    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(arrowStartX, arrowStartY);
    ctx.lineTo(arrowEndX, arrowEndY);
    ctx.stroke();

    ctx.fillStyle = "#facc15";
    ctx.beginPath();
    ctx.arc(arrowStartX, arrowStartY, 3.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.font = "9px 'JetBrains Mono', monospace";
    ctx.fillText(`SUN AZ ${sunGeom.az.toFixed(0)}°`, arrowStartX - 28, arrowStartY - 10);

    ctx.restore();
  }, [
    zoom,
    pan,
    layers,
    currentStep,
    dashOffset,
    getSlopeAt,
    getElevationAt,
    getMLHazardAt,
    isPointLit,
    isPointEarthVisible,
    getSunGeometryAt,
  ]);

  // Point Inspector & Real-Time Coordinate HUD
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

    const scale = (EXTENT_M * 2) / canvas.width;
    const dx = (px - (canvas.width / 2 + pan.x)) / zoom;
    const dy = (py - (canvas.height / 2 + pan.y)) / zoom;
    const xM = dx * scale;
    const yM = -dy * scale;

    const slope = getSlopeAt(xM, yM);
    const elev = getElevationAt(xM, yM);
    const distM = Math.sqrt(xM * xM + yM * yM);
    const lat = 90.0 - distM / 30300.0;
    const lon = (Math.atan2(xM, -yM) * 180.0) / Math.PI;
    const lit = isPointLit(xM, yM, currentStep);
    const earthVis = isPointEarthVisible(xM, yM);
    const isPSR = distM < 1850.0;
    const mlHazard = getMLHazardAt(xM, yM);
    const isTerrainHazard = slope > layers.maxSlopeLimit;
    const isMLHazard = mlHazard.detected && mlHazard.confidence >= layers.mlConfidenceThreshold;
    const isFusedHazard = isTerrainHazard || isMLHazard;

    setCursorHud({
      xM: Math.round(xM),
      yM: Math.round(yM),
      elev: Math.round(elev),
      slope: Math.round(slope * 10) / 10,
      lat: Math.round(lat * 1000) / 1000,
      lon: Math.round((lon >= 0 ? lon : lon + 360) * 10) / 10,
    });

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
    <div className="flex flex-col gap-3 w-full" style={{ width: "100%" }}>
      <div
        className="relative w-full rounded-2xl overflow-hidden border border-white/10 bg-slate-950 shadow-2xl"
        style={{ width: "100%", height: 600, minHeight: 600, position: "relative" }}
      >
        <canvas
          ref={canvasRef}
          width={880}
          height={600}
          onMouseMove={handleMouseMove}
          onMouseDown={(e) => {
            setIsDragging(true);
            const rect = e.currentTarget.getBoundingClientRect();
            setDragStart({ x: e.clientX - rect.left, y: e.clientY - rect.top });
          }}
          onMouseUp={() => setIsDragging(false)}
          onMouseLeave={() => {
            setIsDragging(false);
            setCursorHud(null);
            onInspect(null);
          }}
          style={{ width: "100%", height: "100%", display: "block", cursor: "crosshair" }}
          aria-label="2D Lunar South Pole Polar Map"
        />

        {/* Top-Left: Target Telemetry Badge */}
        <div className="absolute top-4 left-4 glass-panel px-3.5 py-2.5 flex flex-col gap-1 text-[11px] font-mono pointer-events-none">
          <div className="flex items-center gap-2 text-sky-300 font-semibold">
            <Compass className="w-3.5 h-3.5 text-sky-400" />
            <span>AOI: SHACKLETON POLAR RIM</span>
          </div>
          <div className="text-gray-400 flex items-center gap-2 text-[10px]">
            <span>CRS: IAU_2015:30100</span>
            <span>•</span>
            <span>R = 1,737.4 km</span>
            <span>•</span>
            <span className="text-sky-300">ZOOM {(zoom * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* Top-Right: Map Control Dock */}
        <div className="absolute top-4 right-4 flex flex-col gap-1.5 glass-panel p-1.5 shadow-xl">
          <button
            onClick={() => setZoom((z) => Math.min(4.0, z * 1.25))}
            aria-label="Zoom In"
            title="Zoom In"
            className="p-2 rounded-lg hover:bg-white/10 text-gray-300 hover:text-sky-300 transition-colors"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoom((z) => Math.max(0.4, z / 1.25))}
            aria-label="Zoom Out"
            title="Zoom Out"
            className="p-2 rounded-lg hover:bg-white/10 text-gray-300 hover:text-sky-300 transition-colors"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setZoom(1.0);
              setPan({ x: 0, y: 0 });
            }}
            aria-label="Reset View"
            title="Reset View"
            className="p-2 rounded-lg hover:bg-white/10 text-gray-300 hover:text-sky-300 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Bottom-Left: Live Real-Time Cursor HUD */}
        <div className="absolute bottom-4 left-4 glass-panel px-3 py-2 text-xs font-mono flex items-center gap-4 pointer-events-none">
          {cursorHud ? (
            <>
              <div className="flex items-center gap-1.5 text-sky-300">
                <Navigation2 className="w-3.5 h-3.5 text-sky-400" />
                <span>
                  {cursorHud.lat.toFixed(3)}°S, {cursorHud.lon.toFixed(1)}°E
                </span>
              </div>
              <div className="text-gray-400">
                X: <strong className="text-white">{cursorHud.xM > 0 ? `+${cursorHud.xM}` : cursorHud.xM}m</strong> | Y:{" "}
                <strong className="text-white">{cursorHud.yM > 0 ? `+${cursorHud.yM}` : cursorHud.yM}m</strong>
              </div>
              <div className="text-gray-400">
                Elev: <strong className="text-emerald-300">{cursorHud.elev} m</strong>
              </div>
              <div className="text-gray-400">
                Slope:{" "}
                <strong className={cursorHud.slope > layers.maxSlopeLimit ? "text-rose-400" : "text-sky-300"}>
                  {cursorHud.slope}°
                </strong>
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2 text-gray-400 text-[11px]">
              <MapPin className="w-3.5 h-3.5 text-sky-400/60" />
              <span>Pan with drag • Hover cursor to inspect point elevation and traversability</span>
            </div>
          )}
        </div>

        {/* Bottom-Right: Metric Scale Bar */}
        <div className="absolute bottom-4 right-4 glass-panel px-3 py-1.5 text-[10px] font-mono text-gray-300 flex flex-col items-end pointer-events-none">
          <div className="flex items-center gap-1 mb-1">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
            <span>SCALE BAR</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-1.5 bg-sky-400/80 border border-white/40 rounded-sm w-20 relative">
              <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-white/60" />
            </div>
            <span className="text-white font-semibold">2.0 km</span>
          </div>
        </div>
      </div>
    </div>
  );
};

// Colormaps
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
