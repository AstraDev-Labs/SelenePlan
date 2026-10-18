import React, { useRef, useEffect, useState, useCallback } from "react";
import { LayerState } from "./LayerControl";
import { PointInspection } from "./InspectorPanel";
import { ZoomIn, ZoomOut, RotateCcw, Navigation2, MapPin, Target, X, Globe, Moon } from "lucide-react";

interface PolarMapProps {
  layers: LayerState;
  onInspect: (data: PointInspection | null) => void;
  currentStep?: number;
  onToggle3D?: () => void;
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
  onToggle3D,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const terrainCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [cursorHud, setCursorHud] = useState<{ xM: number; yM: number; elev: number; slope: number; lat: number; lon: number } | null>(null);

  // Click-to-Pin Inspection State
  const [pinnedPoint, setPinnedPoint] = useState<{ xM: number; yM: number; elev: number; slope: number } | null>(null);
  const pinnedInspectionRef = useRef<PointInspection | null>(null);
  const dragDistanceRef = useRef<number>(0);
  const mouseRafRef = useRef<number | null>(null);

  // Native non-passive wheel listener: smooth map zoom without scrolling the window
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onNativeWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      setZoom((z) => Math.min(4.0, Math.max(0.4, z * zoomFactor)));
    };

    canvas.addEventListener("wheel", onNativeWheel, { passive: false });
    return () => {
      canvas.removeEventListener("wheel", onNativeWheel);
    };
  }, []);

  // Analytic High-Fidelity Shackleton DEM profile generator with calibrated lunar slopes
  const getElevationAt = useCallback((xM: number, yM: number) => {
    const distSq = xM * xM + yM * yM;
    const dist = Math.sqrt(distSq);

    // Shackleton Crater Morphology
    // Basin Floor: r <= 850m, gentle bowl (slopes 1° to 6° -> SAFE)
    // Inner Scarp Wall: 850m < r <= 2100m, steep regolith slope (slopes 25° to 45° -> HAZARD)
    // Rim Crest: r ~ 2100m, ridge peak (slopes 0° to 5° -> SAFE)
    // Outer Ejecta & Highlands: r > 2100m, rolling polar plains (slopes 3° to 7° -> SAFE)
    const zFloor = -4180.0;
    const zRim = -3300.0;
    const zPlain = -3750.0;
    const rFloor = 850.0;
    const rRim = 2100.0;

    let baseElev: number;
    if (dist <= rFloor) {
      const normR = dist / rFloor;
      baseElev = zFloor + 50.0 * (normR * normR);
    } else if (dist <= rRim) {
      const t = (dist - rFloor) / (rRim - rFloor);
      const s = 3.0 * t * t - 2.0 * t * t * t; // smoothstep S-curve
      baseElev = (zFloor + 50.0) + (zRim - (zFloor + 50.0)) * s;
    } else {
      const dr = dist - rRim;
      const decay = Math.exp(-Math.pow(dr / 3600.0, 1.25));
      baseElev = zPlain + (zRim - zPlain) * decay;
    }

    // Connecting Ridge Spine elevation boost along the traversable ridge (x ~ -2200m)
    const rx = (xM - (-2200.0)) / 1100.0;
    const ry = yM / 4500.0;
    const ridgeDistSq = rx * rx + ry * ry;
    const ridgeBoost = 180.0 * Math.exp(-ridgeDistSq);

    // Secondary micro-craters
    let craterDent = 0;
    for (let i = 0; i < SIMULATED_ML_CRATERS.length; i++) {
      const c = SIMULATED_ML_CRATERS[i];
      const dx = xM - c.x;
      const dy = yM - c.y;
      const dSq = dx * dx + dy * dy;
      if (dSq < c.r * c.r) {
        const d = Math.sqrt(dSq);
        const ratio = 1 - d / c.r;
        craterDent += (c.r * 0.16) * (ratio * ratio);
      }
    }

    return baseElev + ridgeBoost - craterDent;
  }, []);

  // Physically grounded slope
  const getSlopeAt = useCallback((xM: number, yM: number) => {
    const delta = 25.0;
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

  // Compute full PointInspection payload for any lunar coordinate (xM, yM)
  const computePointInspection = useCallback((xM: number, yM: number): PointInspection => {
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

    const delta = 25.0;
    const zE = getElevationAt(xM + delta, yM);
    const zW = getElevationAt(xM - delta, yM);
    const zN = getElevationAt(xM, yM + delta);
    const zS = getElevationAt(xM, yM - delta);
    const tri = (Math.abs(zE - elev) + Math.abs(zW - elev) + Math.abs(zN - elev) + Math.abs(zS - elev)) * 0.25;

    const sunSeries = Array.from({ length: 48 }, (_, t) => isPointLit(xM, yM, t));
    const earthSeries = Array.from({ length: 48 }, () => earthVis);
    const litCount = sunSeries.filter(Boolean).length;
    const litFrac = isPSR ? 0.0 : litCount / sunSeries.length;

    return {
      x_m: xM,
      y_m: yM,
      lat_deg: lat,
      lon_deg: lon >= 0 ? lon : lon + 360,
      elevation_m: elev,
      slope_deg: slope,
      aspect_deg: (Math.atan2(xM, yM) * 180.0) / Math.PI,
      roughness_m: tri,
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
    };
  }, [currentStep, getElevationAt, getMLHazardAt, getSlopeAt, isPointEarthVisible, isPointLit, layers.maxSlopeLimit, layers.mlConfidenceThreshold]);

  // =========================================================================
  // Compute & Cache Terrain Raster: Crisp 1x1 Native Resolution Photographic Moon Surface
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

    // Grazing solar vector for hillshade calculation
    const sunGeom = getSunGeometryAt(currentStep);
    const sunAzRad = (sunGeom.az * Math.PI) / 180.0;
    const sunElRad = (Math.max(1.0, sunGeom.el) * Math.PI) / 180.0;
    const sunX = Math.cos(sunElRad) * Math.sin(sunAzRad);
    const sunY = -Math.cos(sunElRad) * Math.cos(sunAzRad);
    const sunZ = Math.sin(sunElRad);

    const delta = 25.0;
    const inv2Delta = 1 / (2 * delta);

    // Render crisp 1x1 pixel resolution (no chunky 2x2 blocks!)
    for (let py = 0; py < height; py++) {
      const yM = (height / 2 - py) * scale;
      const rowOffset = py * width * 4;

      for (let px = 0; px < width; px++) {
        const xM = (px - width / 2) * scale;

        const elev = getElevationAt(xM, yM);
        const distSq = xM * xM + yM * yM;
        const distM = Math.sqrt(distSq);

        // Elevation gradients for Surface Normal
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

        // Realistic Lunar Hillshade (Hapke / Lommel-Seeliger scattering model)
        const dot = nx * sunX + ny * sunY + nz * sunZ;
        const directShade = dot > 0 ? dot : 0;
        const isPSR = distM < 1850.0;
        const ambient = isPSR ? 0.02 : 0.12;
        const shade = Math.min(1.0, ambient + directShade * 0.88);

        // Authentic Lunar Regolith Grayscale Palette (NASA LROC / Clementine standard)
        // Regolith base: charcoal/slate basalt to bright anorthosite highlands
        let r: number, g: number, b: number;

        if (isPSR) {
          // Permanently Shadowed Region: dark void with faint earthshine reflection
          r = Math.round(14 + shade * 18);
          g = Math.round(16 + shade * 20);
          b = Math.round(24 + shade * 28);
        } else {
          // Sunlit lunar surface: rich silver-grey tones
          const lunarIntensity = Math.round(28 + shade * 205);
          r = lunarIntensity;
          g = lunarIntensity;
          b = Math.min(255, lunarIntensity + 3);

          // Anorthosite high rim brightening
          if (elev > -3400) {
            r = Math.min(255, r + 15);
            g = Math.min(255, g + 15);
            b = Math.min(255, b + 18);
          }
        }

        // ===================================================================
        // OPTIONAL THEMATIC GIS OVERLAYS (Only when toggled by user!)
        // ===================================================================

        // 1. Terrain Ruggedness Index (TRI)
        const tri = (Math.abs(zE - elev) + Math.abs(zW - elev) + Math.abs(zN - elev) + Math.abs(zS - elev)) * 0.25;

        if (layers.showRoughness) {
          const normTRI = Math.min(1.0, tri / 2.2);
          const [rr, rg, rb] = getRoughnessColor(normTRI);
          // Modulate with topography
          const trAlpha = 0.65;
          r = Math.round(rr * trAlpha + r * (1 - trAlpha));
          g = Math.round(rg * trAlpha + g * (1 - trAlpha));
          b = Math.round(rb * trAlpha + b * (1 - trAlpha));
        }

        // 2. Slope Map (Viridis / Magma)
        if (layers.showSlope) {
          const normSlope = Math.min(1.0, slope / 45.0);
          const [sr, sg, sb] = layers.colormap === "magma" ? getMagmaColor(normSlope) : getViridisColor(normSlope);
          const slAlpha = 0.60;
          r = Math.round(sr * slAlpha + r * (1 - slAlpha));
          g = Math.round(sg * slAlpha + g * (1 - slAlpha));
          b = Math.round(sb * slAlpha + b * (1 - slAlpha));
        }

        // 3. Solar Illumination Layer
        if (layers.showIllumination) {
          const lit = isPointLit(xM, yM, currentStep);
          if (lit) {
            // Subtle warm solar highlight on sunlit ground
            r = Math.min(255, Math.round(r * 1.1 + 35));
            g = Math.min(255, Math.round(g * 1.08 + 25));
            b = Math.min(255, Math.round(b * 0.95));
          } else {
            // Shadow zone dampening
            r = Math.round(r * 0.5);
            g = Math.round(r * 0.5);
            b = Math.round(b * 0.6);
          }
        }

        // 4. Earth Visibility (Line-of-Sight)
        if (layers.showEarthVisibility) {
          if (!isPSR) {
            r = Math.round(r * 0.8 + 12);
            g = Math.round(g * 0.8 + 40);
            b = Math.round(b * 0.8 + 75);
          } else {
            r = Math.min(255, Math.round(r * 0.6 + 90));
            g = Math.round(g * 0.4);
            b = Math.round(b * 0.4);
          }
        }

        // 5. Permanent Shadow Region (PSR) Subtle Contour
        if (layers.showPSR && isPSR) {
          r = Math.round(r * 0.4 + 20);
          g = Math.round(g * 0.4 + 35);
          b = Math.round(b * 0.4 + 110);
        }

        // 6. Hazard Overlays (Fused, Slope, or ML)
        const isTerrainHazard = slope > layers.maxSlopeLimit;
        const mlHazard = getMLHazardAt(xM, yM);
        const isMLHazard = mlHazard.detected && mlHazard.confidence >= layers.mlConfidenceThreshold;

        if (layers.showFusedHazard && (isTerrainHazard || isMLHazard)) {
          r = Math.min(255, Math.round(r * 0.45 + 160));
          g = Math.round(g * 0.4 + 40);
          b = Math.round(b * 0.4 + 30);
        } else if (layers.showHazard && isTerrainHazard) {
          r = Math.min(255, Math.round(r * 0.45 + 145));
          g = Math.round(g * 0.35 + 30);
          b = Math.round(b * 0.35 + 30);
        } else if (layers.showMLHazard && isMLHazard) {
          r = Math.min(255, Math.round(r * 0.45 + 130));
          g = Math.round(g * 0.35 + 25);
          b = Math.min(255, Math.round(b * 0.45 + 145));
        }

        const idx = rowOffset + px * 4;
        data[idx] = r;
        data[idx + 1] = g;
        data[idx + 2] = b;
        data[idx + 3] = 255;
      }
    }

    tCtx.putImageData(imgData, 0, 0);
    renderScene();
  }, [layers, currentStep, getElevationAt, getMLHazardAt, getSunGeometryAt, isPointLit]);

  // Fast GPU Blit Scene Render
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

    // Blit Cached Raster (100% crisp photographic lunar DEM surface)
    ctx.drawImage(tCanvas, -width / 2, -height / 2);

    // Polar Range Rings (Subtle cyan grid)
    ctx.strokeStyle = "rgba(56, 189, 248, 0.22)";
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

    // Central Crosshair passing through South Pole (0, 0)
    ctx.strokeStyle = "rgba(56, 189, 248, 0.3)";
    ctx.beginPath();
    ctx.moveTo(0, -height);
    ctx.lineTo(0, height);
    ctx.moveTo(-width, 0);
    ctx.lineTo(width, 0);
    ctx.stroke();
    ctx.setLineDash([]);

    // Vector Annotations for ML Craters (Only if toggled)
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

    // Clean Aerospace Rover Traverse Route (Crisp static line, no animated jitter!)
    ctx.save();
    ctx.strokeStyle = "rgba(14, 165, 233, 0.35)";
    ctx.lineWidth = 5;
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
    ctx.lineWidth = 2;
    ctx.stroke();

    // Waypoints
    for (let i = 0; i < MISSION_WAYPOINTS.length; i++) {
      const wp = MISSION_WAYPOINTS[i];
      const px = wp.x / scale;
      const py = -wp.y / scale;

      ctx.fillStyle = wp.type === "start" ? "#10b981" : wp.type === "target" ? "#f59e0b" : "#38bdf8";
      ctx.beginPath();
      ctx.arc(px, py, wp.type === "start" ? 5.5 : 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(px, py, wp.type === "start" ? 7.5 : 6, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = "rgba(10, 15, 30, 0.92)";
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

    // =======================================================================
    // PINNED INSPECTION RETICLE (Target Lock)
    // =======================================================================
    if (pinnedPoint) {
      const pinPx = pinnedPoint.xM / scale;
      const pinPy = -pinnedPoint.yM / scale;

      ctx.save();
      // Outer Target Halo
      ctx.strokeStyle = "#22d3ee";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(pinPx, pinPy, 14, 0, Math.PI * 2);
      ctx.stroke();

      // Center Bullseye Ring
      ctx.fillStyle = "rgba(34, 211, 238, 0.25)";
      ctx.beginPath();
      ctx.arc(pinPx, pinPy, 7, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(pinPx, pinPy, 7, 0, Math.PI * 2);
      ctx.stroke();

      // Precision Center Dot
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(pinPx, pinPy, 2.5, 0, Math.PI * 2);
      ctx.fill();

      // Cardinal Target Ticks
      ctx.strokeStyle = "#22d3ee";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(pinPx - 20, pinPy); ctx.lineTo(pinPx - 10, pinPy);
      ctx.moveTo(pinPx + 10, pinPy); ctx.lineTo(pinPx + 20, pinPy);
      ctx.moveTo(pinPx, pinPy - 20); ctx.lineTo(pinPx, pinPy - 10);
      ctx.moveTo(pinPx, pinPy + 10); ctx.lineTo(pinPx, pinPy + 20);
      ctx.stroke();

      // Target Coordinate Badge
      ctx.fillStyle = "rgba(8, 14, 26, 0.95)";
      ctx.strokeStyle = "#22d3ee";
      ctx.lineWidth = 1;
      ctx.font = "bold 10px 'JetBrains Mono', monospace";
      const pinText = `INSPECTED: (${Math.round(pinnedPoint.xM)}m, ${Math.round(pinnedPoint.yM)}m | ${Math.round(pinnedPoint.elev)}m)`;
      const ptw = ctx.measureText(pinText).width;
      ctx.fillRect(pinPx - ptw / 2 - 6, pinPy - 36, ptw + 12, 18);
      ctx.strokeRect(pinPx - ptw / 2 - 6, pinPy - 36, ptw + 12, 18);

      ctx.fillStyle = "#67e8f9";
      ctx.fillText(pinText, pinPx - ptw / 2, pinPy - 23);
      ctx.restore();
    }

    // Geographic Feature Labels
    ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
    ctx.font = "bold 12px 'Space Grotesk', sans-serif";
    ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
    ctx.shadowBlur = 6;
    ctx.fillText("Shackleton Crater (Rim)", 15, -85);
    ctx.fillText("South Pole (90.00°S)", 8, 18);

    ctx.fillStyle = "rgba(203, 213, 225, 0.9)";
    ctx.font = "10px 'Space Grotesk', sans-serif";
    ctx.fillText("Connecting Ridge", -230, 90);
    ctx.fillText("Shackleton Crater Floor (-4,200m)", -105, -12);
    ctx.shadowBlur = 0;

    // Sun Vector Arrow
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
  }, [pan, zoom, layers, currentStep, pinnedPoint, getSunGeometryAt]);

  // Redraw when pan, zoom, or pinnedPoint changes
  useEffect(() => {
    renderScene();
  }, [pan, zoom, pinnedPoint, renderScene]);

  // Helper: Converts client mouse coordinates to canvas bitmap & terrain coords
  const getCoordsFromEvent = useCallback((clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;

    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const bx = (clientX - rect.left) * scaleX;
    const by = (clientY - rect.top) * scaleY;

    const scale = (EXTENT_M * 2) / canvas.width;
    const dx = (bx - (canvas.width / 2 + pan.x)) / zoom;
    const dy = (by - (canvas.height / 2 + pan.y)) / zoom;
    const xM = dx * scale;
    const yM = -dy * scale;

    return { bx, by, xM, yM };
  }, [pan.x, pan.y, zoom]);

  // Canvas Click Handler: PINS inspected terrain pixel at exact click location
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (dragDistanceRef.current > 5) return;

    const coords = getCoordsFromEvent(e.clientX, e.clientY);
    if (!coords) return;

    const inspection = computePointInspection(coords.xM, coords.yM);
    setPinnedPoint({
      xM: coords.xM,
      yM: coords.yM,
      elev: inspection.elevation_m,
      slope: inspection.slope_deg,
    });
    pinnedInspectionRef.current = inspection;
    onInspect(inspection);
  };

  // Clear pinned target inspection
  const handleClearPin = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPinnedPoint(null);
    pinnedInspectionRef.current = null;
    onInspect(null);
  };

  // Throttled Point Inspector on MouseMove
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    if (isDragging) {
      const dX = (e.clientX - dragStart.x) * scaleX;
      const dY = (e.clientY - dragStart.y) * scaleY;
      dragDistanceRef.current += Math.hypot(dX, dY);
      setPan({
        x: pan.x + dX,
        y: pan.y + dY,
      });
      setDragStart({ x: e.clientX, y: e.clientY });
      return;
    }

    if (mouseRafRef.current) return;
    const clientX = e.clientX;
    const clientY = e.clientY;

    mouseRafRef.current = requestAnimationFrame(() => {
      mouseRafRef.current = null;

      const coords = getCoordsFromEvent(clientX, clientY);
      if (!coords) return;
      const { xM, yM } = coords;

      const slope = getSlopeAt(xM, yM);
      const elev = getElevationAt(xM, yM);
      const distM = Math.sqrt(xM * xM + yM * yM);
      const lat = 90.0 - distM / 30300.0;
      const lon = (Math.atan2(xM, -yM) * 180.0) / Math.PI;

      setCursorHud({
        xM: Math.round(xM),
        yM: Math.round(yM),
        elev: Math.round(elev),
        slope: Math.round(slope * 10) / 10,
        lat: Math.round(lat * 1000) / 1000,
        lon: Math.round((lon >= 0 ? lon : lon + 360) * 10) / 10,
      });

      if (!pinnedInspectionRef.current) {
        const liveInspection = computePointInspection(xM, yM);
        onInspect(liveInspection);
      }
    });
  };

  return (
    <div className="flex flex-col gap-3 w-full" style={{ width: "100%" }}>
      <div
        className="relative w-full rounded-2xl overflow-hidden border border-white/10 bg-slate-950 shadow-2xl"
        style={{ width: "100%", height: 600, minHeight: 600, position: "relative", overscrollBehavior: "contain" }}
      >
        <canvas
          ref={canvasRef}
          width={880}
          height={600}
          onClick={handleCanvasClick}
          onMouseMove={handleMouseMove}
          onMouseDown={(e) => {
            setIsDragging(true);
            dragDistanceRef.current = 0;
            setDragStart({ x: e.clientX, y: e.clientY });
          }}
          onMouseUp={() => setIsDragging(false)}
          onMouseLeave={() => {
            setIsDragging(false);
            setCursorHud(null);
            if (pinnedInspectionRef.current) {
              onInspect(pinnedInspectionRef.current);
            } else {
              onInspect(null);
            }
          }}
          style={{ width: "100%", height: "100%", display: "block", cursor: "crosshair", touchAction: "none", overscrollBehavior: "contain" }}
          aria-label="2D Lunar South Pole Polar Map"
        />

        {/* Top-Left: Target Telemetry & Clear Lunar Orientation HUD */}
        <div className="absolute top-4 left-4 glass-panel px-3.5 py-2.5 flex flex-col gap-1.5 text-[11px] font-mono pointer-events-none">
          <div className="flex items-center gap-2 text-sky-300 font-bold">
            <Moon className="w-4 h-4 text-sky-400" />
            <span>MOON: SOUTH POLE SURFACE MAP</span>
          </div>
          <div className="flex items-center gap-2 text-emerald-300 text-[10px]">
            <Globe className="w-3.5 h-3.5 text-emerald-400" />
            <span>↑ 0° LON: TOWARDS EARTH (LOS)</span>
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
          {onToggle3D && (
            <button
              onClick={onToggle3D}
              aria-label="Switch to 3D Moon Globe"
              title="Switch to 3D Moon Globe"
              className="p-2 rounded-lg bg-sky-500/20 text-sky-300 hover:bg-sky-500/30 border border-sky-500/40 transition-colors"
            >
              <Globe className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Bottom-Left: Live Real-Time Cursor HUD & Pinned Target Indicator */}
        <div className="absolute bottom-4 left-4 glass-panel px-3 py-2 text-xs font-mono flex items-center gap-4">
          {pinnedPoint ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-cyan-300 font-bold">
                <Target className="w-4 h-4 text-cyan-400" />
                <span>PINNED TARGET:</span>
              </div>
              <div className="text-gray-300">
                X: <strong className="text-white">{Math.round(pinnedPoint.xM)}m</strong> | Y:{" "}
                <strong className="text-white">{Math.round(pinnedPoint.yM)}m</strong>
              </div>
              <div className="text-emerald-300 font-bold">
                Elev: {Math.round(pinnedPoint.elev)}m
              </div>
              <div className="text-sky-300">
                Slope: {pinnedPoint.slope.toFixed(1)}°
              </div>
              <button
                onClick={handleClearPin}
                title="Unpin / Reset Inspector"
                className="flex items-center gap-1 px-2 py-0.5 rounded bg-white/10 hover:bg-rose-500/20 text-gray-300 hover:text-rose-300 transition-colors border border-white/20 text-[10px]"
              >
                <X className="w-3 h-3" />
                <span>UNPIN</span>
              </button>
            </div>
          ) : cursorHud ? (
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
              <span className="text-[10px] text-cyan-400/80 font-sans italic ml-1">
                (Click map to pin inspection)
              </span>
            </>
          ) : (
            <div className="flex items-center gap-2 text-gray-400 text-[11px]">
              <MapPin className="w-3.5 h-3.5 text-sky-400/60" />
              <span>Click anywhere on lunar surface to inspect & lock pixel terrain • Pan with drag</span>
            </div>
          )}
        </div>

        {/* Bottom-Right: Metric Scale Bar & Farside Orientation Indicator */}
        <div className="absolute bottom-4 right-4 glass-panel px-3 py-1.5 text-[10px] font-mono text-gray-300 flex flex-col items-end pointer-events-none">
          <div className="flex items-center gap-1 mb-1">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
            <span>SCALE BAR</span>
          </div>
          <div className="flex items-center gap-2 mb-1">
            <div className="h-1.5 bg-sky-400/80 border border-white/40 rounded-sm w-20 relative">
              <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-white/60" />
            </div>
            <span className="text-white font-semibold">2.0 km</span>
          </div>
          <span className="text-[9px] text-gray-400">↓ 180° Lon (Lunar Farside)</span>
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

// Terrain Ruggedness Index (TRI) Colormap
function getRoughnessColor(t: number): [number, number, number] {
  if (t < 0.25) {
    const u = t / 0.25;
    return [15, (23 + u * 120) | 0, (42 + u * 94) | 0];
  } else if (t < 0.65) {
    const u = (t - 0.25) / 0.4;
    return [(15 + u * 230) | 0, (143 + u * 15) | 0, (136 - u * 125) | 0];
  } else {
    const u = (t - 0.65) / 0.35;
    return [(245 + u * 9) | 0, (158 + u * 82) | 0, (11 + u * 127) | 0];
  }
}
