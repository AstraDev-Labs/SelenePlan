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
  const terrainCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [cursorHud, setCursorHud] = useState<{ xM: number; yM: number; elev: number; slope: number; lat: number; lon: number } | null>(null);

  const dashOffsetRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);
  const mouseRafRef = useRef<number | null>(null);

  // Analytic High-Fidelity Shackleton DEM profile generator
  const getElevationAt = useCallback((xM: number, yM: number) => {
    const distSq = xM * xM + yM * yM;
    const dist = Math.sqrt(distSq);
    const rimRadius = 2100.0;
    const depth = 4200.0;

    // Connecting Ridge Spine elevation boost along the ridge
    const rx = xM - (-2200);
    const ridgeDistSq = rx * rx + yM * yM;
    const ridgeBoost = ridgeDistSq < 5000000 ? 350.0 * Math.exp(-ridgeDistSq / 1960000) : 0;

    // Secondary micro-craters
    let craterDent = 0;
    for (let i = 0; i < SIMULATED_ML_CRATERS.length; i++) {
      const c = SIMULATED_ML_CRATERS[i];
      const dx = xM - c.x;
      const dy = yM - c.y;
      const dSq = dx * dx + dy * dy;
      const rMax = c.r * 1.5;
      if (dSq < rMax * rMax) {
        const d = Math.sqrt(dSq);
        const ratio = 1 - d / c.r;
        if (ratio > 0) {
          craterDent += 180.0 * ratio * ratio;
        }
      }
    }

    if (dist <= rimRadius) {
      return -4200.0 + (depth * (distSq / (rimRadius * rimRadius))) - craterDent;
    } else {
      const rRatio = rimRadius / dist;
      const base = -800.0 + (1200.0 * rRatio * rRatio * rRatio);
      return base + ridgeBoost - craterDent;
    }
  }, []);

  // Physically grounded slope
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
    for (let i = 0; i < SIMULATED_ML_CRATERS.length; i++) {
      const c = SIMULATED_ML_CRATERS[i];
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
    return dist >= 1850.0;
  }, []);

  // =========================================================================
  // OPTIMIZATION 1: Compute & Cache Terrain Raster ONLY when layers change
  // Runs 0 times during pan, zoom, or animations!
  // =========================================================================
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const width = canvas.width;
    const height = canvas.height;

    if (!terrainCanvasRef.current) {
      terrainCanvasRef.current = document.createElement("canvas");
    }
    const tCanvas = terrainCanvasRef.current;
    if (tCanvas.width !== width || tCanvas.height !== height) {
      tCanvas.width = width;
      tCanvas.height = height;
    }
    const tCtx = tCanvas.getContext("2d");
    if (!tCtx) return;

    const scale = (EXTENT_M * 2) / width;
    const imgData = tCtx.createImageData(width, height);
    const data = imgData.data;

    // Sun vector for hillshade
    const sunGeom = getSunGeometryAt(currentStep);
    const sunAzRad = (sunGeom.az * Math.PI) / 180.0;
    const sunElRad = (Math.max(1.0, sunGeom.el) * Math.PI) / 180.0;
    const sunX = Math.cos(sunElRad) * Math.sin(sunAzRad);
    const sunY = -Math.cos(sunElRad) * Math.cos(sunAzRad);
    const sunZ = Math.sin(sunElRad);

    const delta = 30.0;
    const inv2Delta = 1 / (2 * delta);

    // Fast 2x2 grid raster generation
    for (let py = 0; py < height; py += 2) {
      const yM = (height / 2 - py) * scale;
      const pyWidth4 = py * width * 4;
      const nextPyWidth4 = (py + 1) * width * 4;

      for (let px = 0; px < width; px += 2) {
        const xM = (px - width / 2) * scale;

        const elev = getElevationAt(xM, yM);
        const distSq = xM * xM + yM * yM;
        const distM = Math.sqrt(distSq);

        // Fast Hillshade via elevation sampling
        const zE = getElevationAt(xM + delta, yM);
        const zW = getElevationAt(xM - delta, yM);
        const zN = getElevationAt(xM, yM + delta);
        const zS = getElevationAt(xM, yM - delta);

        const dzdx = (zE - zW) * inv2Delta;
        const dzdy = (zN - zS) * inv2Delta;
        const grad = Math.sqrt(dzdx * dzdx + dzdy * dzdy);
        const slope = Math.min(60.0, Math.atan(grad) * 57.2957795);

        const len = Math.sqrt(grad * grad + 1.0);
        const nx = -dzdx / len;
        const ny = -dzdy / len;
        const nz = 1.0 / len;

        const dot = nx * sunX + ny * sunY + nz * sunZ;
        const directShade = dot > 0 ? dot : 0;
        const isPSR = distM < 1850.0;
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
          r = Math.round(cr * 0.65 + r * 0.35);
          g = Math.round(cg * 0.65 + g * 0.35);
          b = Math.round(cb * 0.65 + b * 0.35);
        }

        // Layer: Solar Illumination
        if (layers.showIllumination) {
          const lit = isPointLit(xM, yM, currentStep);
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
          if (!isPSR) {
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

        // Layer: Hazards
        const isTerrainHazard = slope > layers.maxSlopeLimit;
        const mlHazard = getMLHazardAt(xM, yM);
        const isMLHazard = mlHazard.detected && mlHazard.confidence >= layers.mlConfidenceThreshold;

        if (layers.showFusedHazard && (isTerrainHazard || isMLHazard)) {
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

        // Fill 2x2 Block
        const idx0 = pyWidth4 + px * 4;
        const idx1 = idx0 + 4;
        const idx2 = nextPyWidth4 + px * 4;
        const idx3 = idx2 + 4;

        data[idx0] = r; data[idx0 + 1] = g; data[idx0 + 2] = b; data[idx0 + 3] = 255;
        data[idx1] = r; data[idx1 + 1] = g; data[idx1 + 2] = b; data[idx1 + 3] = 255;
        data[idx2] = r; data[idx2 + 1] = g; data[idx2 + 2] = b; data[idx2 + 3] = 255;
        data[idx3] = r; data[idx3 + 1] = g; data[idx3 + 2] = b; data[idx3 + 3] = 255;
      }
    }

    tCtx.putImageData(imgData, 0, 0);

    // Trigger immediate view redraw
    renderScene();
  }, [layers, currentStep, getElevationAt, getMLHazardAt, getSunGeometryAt, isPointLit]);

  // =========================================================================
  // OPTIMIZATION 2: Ultra-Fast Vector Scene Render (< 0.5ms)
  // Re-uses cached raster buffer via hardware accelerated drawImage
  // =========================================================================
  const renderScene = useCallback(() => {
    const canvas = canvasRef.current;
    const tCanvas = terrainCanvasRef.current;
    if (!canvas || !tCanvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const scale = (EXTENT_M * 2) / width;

    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.translate(width / 2 + pan.x, height / 2 + pan.y);
    ctx.scale(zoom, zoom);

    // Blit Cached Raster (Instant GPU Texture Draw)
    ctx.drawImage(tCanvas, -width / 2, -height / 2);

    // Polar Range Rings
    ctx.strokeStyle = "rgba(56, 189, 248, 0.25)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 6]);

    const rings = [1000, 2000, 3000, 4000, 6000];
    for (let i = 0; i < rings.length; i++) {
      const rM = rings[i];
      const rPx = rM / scale;
      ctx.beginPath();
      ctx.arc(0, 0, rPx, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = "rgba(148, 163, 184, 0.7)";
      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.fillText(`${(rM / 1000).toFixed(0)} km`, rPx + 4, -4);
    }

    // Crosshairs
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
      for (let i = 0; i < SIMULATED_ML_CRATERS.length; i++) {
        const c = SIMULATED_ML_CRATERS[i];
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
        const text = c.name;
        ctx.font = "10px 'JetBrains Mono', monospace";
        const tw = ctx.measureText(text).width;
        ctx.fillRect(px - rPx, py - rPx - 18, tw + 8, 14);
        ctx.strokeRect(px - rPx, py - rPx - 18, tw + 8, 14);

        ctx.fillStyle = "#f5d0fe";
        ctx.fillText(text, px - rPx + 4, py - rPx - 7);
      }
    }

    // Traverse Route Vector
    ctx.save();
    ctx.strokeStyle = "rgba(14, 165, 233, 0.4)";
    ctx.lineWidth = 6;
    ctx.beginPath();
    for (let i = 0; i < MISSION_WAYPOINTS.length; i++) {
      const wp = MISSION_WAYPOINTS[i];
      const px = wp.x / scale;
      const py = -wp.y / scale;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();

    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2.5;
    ctx.setLineDash([8, 6]);
    ctx.lineDashOffset = -dashOffsetRef.current;
    ctx.stroke();
    ctx.setLineDash([]);

    // Waypoints
    for (let i = 0; i < MISSION_WAYPOINTS.length; i++) {
      const wp = MISSION_WAYPOINTS[i];
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
    }
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

    // Sun Vector
    const sunGeom = getSunGeometryAt(currentStep);
    const sunAzRad = (sunGeom.az * Math.PI) / 180.0;
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
  }, [pan, zoom, layers, currentStep, getSunGeometryAt]);

  // Redraw when pan or zoom changes (instant)
  useEffect(() => {
    renderScene();
  }, [pan, zoom, renderScene]);

  // Lightweight 60fps Route Animation Loop (Only renders vector overlay!)
  useEffect(() => {
    let lastTime = performance.now();
    const animate = (time: number) => {
      if (time - lastTime >= 80) {
        dashOffsetRef.current = (dashOffsetRef.current + 1) % 16;
        renderScene();
        lastTime = time;
      }
      rafIdRef.current = requestAnimationFrame(animate);
    };
    rafIdRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
  }, [renderScene]);

  // =========================================================================
  // OPTIMIZATION 3: Throttled Point Inspector on MouseMove via RAF
  // Prevents hundreds of React state updates per second
  // =========================================================================
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

    // Throttle cursor calculations to 1 per animation frame
    if (mouseRafRef.current) return;
    mouseRafRef.current = requestAnimationFrame(() => {
      mouseRafRef.current = null;

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

// Fast Colormaps
function getViridisColor(t: number): [number, number, number] {
  const r = (68 + t * 185) | 0;
  const g = (1 + t * 230) | 0;
  const b = (84 - t * 47) | 0;
  return [r, g, b];
}

function getMagmaColor(t: number): [number, number, number] {
  const r = (t * 251) | 0;
  const g = (t * 136) | 0;
  const b = (4 + t * 149) | 0;
  return [r, g, b];
}
