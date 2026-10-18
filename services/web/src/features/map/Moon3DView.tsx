import React, { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import {
  RotateCw,
  Sun,
  Globe,
  Moon,
  MapPin,
  Navigation,
  Compass,
  Target,
  X,
  ShieldAlert,
  CheckCircle2,
} from "lucide-react";
import { PointInspection } from "./InspectorPanel";
import { LayerState } from "./LayerControl";

interface Moon3DViewProps {
  step?: number;
  onToggle2D?: () => void;
  onInspect?: (data: PointInspection | null) => void;
  layers?: LayerState;
}

interface Landmark {
  id: string;
  name: string;
  category: "artemis" | "apollo" | "psr" | "ridge";
  lat: number;
  lon: number;
  elevM: number;
  description: string;
  details: string;
}

const LUNAR_LANDMARKS: Landmark[] = [
  {
    id: "shackleton",
    name: "Shackleton Crater (AOI)",
    category: "artemis",
    lat: -89.9,
    lon: 0.0,
    elevM: -4180,
    description: "Primary Artemis III Exploration Zone. Permanently Shadowed Cold Trap with H2O Ice Volatiles.",
    details: "Diameter: 21 km | Basin Depth: 4.2 km | Sunlit Rim: >86% annually",
  },
  {
    id: "connecting_ridge",
    name: "Connecting Ridge",
    category: "ridge",
    lat: -89.4,
    lon: -137.0,
    elevM: 390,
    description: "Traversable high-elevation corridor connecting Shackleton and de Gerlache crater rims.",
    details: "Max slope: <8° along spine | High continuous Direct-to-Earth comms",
  },
  {
    id: "eternal_light",
    name: "Peak of Eternal Light",
    category: "artemis",
    lat: -89.8,
    lon: -122.0,
    elevM: 420,
    description: "High sunlit mountain peak receiving near-constant solar flux (92% during lunar summer).",
    details: "Ideal site for solar power generation and thermal survival",
  },
  {
    id: "de_gerlache",
    name: "de Gerlache Rim",
    category: "psr",
    lat: -88.5,
    lon: -88.3,
    elevM: -2100,
    description: "Deep ancient impact crater with extensive sub-surface water-ice signatures.",
    details: "Diameter: 32.4 km | Direct line-of-sight to Earth",
  },
  {
    id: "malapert",
    name: "Malapert Mountain (Massif)",
    category: "artemis",
    lat: -86.0,
    lon: 2.7,
    elevM: 5000,
    description: "Towering 5,000m massif providing uninterrupted line-of-sight communications to Earth.",
    details: "Permanent Earth visibility | Candidate comms relay mast site",
  },
  {
    id: "apollo_11",
    name: "Apollo 11 Tranquility Base",
    category: "apollo",
    lat: 0.67,
    lon: 23.47,
    elevM: -1400,
    description: "Historical first crewed lunar landing site (Neil Armstrong & Buzz Aldrin, July 20, 1969).",
    details: "Mare Tranquillitatis | Basaltic lava plain",
  },
];

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

function polarStereoToLatLon(xM: number, yM: number): { lat: number; lon: number } {
  const dist = Math.hypot(xM, yM);
  const colatRad = dist / 1737400.0;
  const lat = -90.0 + (colatRad * 180.0) / Math.PI;
  let lon = (Math.atan2(xM, -yM) * 180.0) / Math.PI;
  if (lon > 180) lon -= 360;
  if (lon < -180) lon += 360;
  return { lat, lon };
}

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

function getTerrainRampColor(t: number): [number, number, number] {
  if (t < 0.25) {
    const u = t / 0.25;
    return [34, (197 - u * 50) | 0, (94 + u * 100) | 0];
  } else if (t < 0.6) {
    const u = (t - 0.25) / 0.35;
    return [(234 - u * 20) | 0, (179 + u * 20) | 0, 8];
  } else {
    const u = (t - 0.6) / 0.4;
    return [(239 + u * 16) | 0, (68 + u * 187) | 0, (68 + u * 187) | 0];
  }
}

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

// Helper: Convert Lunar Lat/Lon (deg) to 3D Cartesian coordinates on sphere of radius R
function latLonToVector3(latDeg: number, lonDeg: number, radius: number): THREE.Vector3 {
  const phi = (90 - latDeg) * (Math.PI / 180);
  const theta = (lonDeg + 180) * (Math.PI / 180);
  const x = -(radius * Math.sin(phi) * Math.cos(theta));
  const z = radius * Math.sin(phi) * Math.sin(theta);
  const y = radius * Math.cos(phi);
  return new THREE.Vector3(x, y, z);
}

// Helper: Convert 3D Cartesian coordinates on sphere of radius R to Lunar Lat/Lon (deg)
function vector3ToLatLon(vec: THREE.Vector3, radius: number = 1.0): { lat: number; lon: number } {
  const normY = Math.max(-1.0, Math.min(1.0, vec.y / radius));
  const phi = Math.acos(normY);
  const lat = 90.0 - (phi * 180.0) / Math.PI;
  const theta = Math.atan2(vec.z, -vec.x);
  let lon = (theta * 180.0) / Math.PI - 180.0;
  while (lon > 180.0) lon -= 360.0;
  while (lon < -180.0) lon += 360.0;
  return { lat, lon };
}

// Topographic Shackleton Elevation Generator for South Pole Region
function getShackletonElev(xM: number, yM: number): number {
  const distSq = xM * xM + yM * yM;
  const dist = Math.sqrt(distSq);
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
    const s = 3.0 * t * t - 2.0 * t * t * t;
    baseElev = (zFloor + 50.0) + (zRim - (zFloor + 50.0)) * s;
  } else {
    const dr = dist - rRim;
    const decay = Math.exp(-Math.pow(dr / 3600.0, 1.25));
    baseElev = zPlain + (zRim - zPlain) * decay;
  }

  const rx = (xM - (-2200.0)) / 1100.0;
  const ry = yM / 4500.0;
  const ridgeDistSq = rx * rx + ry * ry;
  const ridgeBoost = 180.0 * Math.exp(-ridgeDistSq);

  return baseElev + ridgeBoost;
}

function getShackletonSlope(xM: number, yM: number): number {
  const delta = 25.0;
  const zE = getShackletonElev(xM + delta, yM);
  const zW = getShackletonElev(xM - delta, yM);
  const zN = getShackletonElev(xM, yM + delta);
  const zS = getShackletonElev(xM, yM - delta);
  const dzdx = (zE - zW) / (2 * delta);
  const dzdy = (zN - zS) / (2 * delta);
  const grad = Math.sqrt(dzdx * dzdx + dzdy * dzdy);
  const slopeDeg = Math.atan(grad) * (180.0 / Math.PI);
  return Math.min(60.0, slopeDeg);
}

// Compute full Lunar Pixel Terrain Inspection
function computeLunarInspection(
  lat: number,
  lon: number,
  step: number,
  maxSlopeLimit: number = 15.0
): PointInspection {
  const isSouthPoleRegion = lat <= -85.0;

  let xM = 0;
  let yM = 0;
  let elev = -1200.0;
  let slope = 4.2;
  let aspect = 90.0;
  let roughness = 0.45;
  let isPSR = false;
  let featureName = "Lunar Highlands";
  let isLit = true;
  let earthVis = true;
  let mlHazard = false;
  let mlConf = 0.0;

  if (isSouthPoleRegion) {
    const distM = (90.0 + lat) * 30300.0;
    const lonRad = (lon * Math.PI) / 180.0;
    xM = distM * Math.sin(lonRad);
    yM = -distM * Math.cos(lonRad);

    elev = getShackletonElev(xM, yM);
    slope = getShackletonSlope(xM, yM);
    roughness = Math.min(2.5, Math.max(0.15, slope * 0.06));
    aspect = (Math.atan2(xM, yM) * 180.0) / Math.PI;

    isPSR = distM < 1850.0;
    earthVis = distM >= 1850.0;
    const el = 1.8 * Math.sin((step / 48) * 2 * Math.PI + 0.3) + 1.2;
    isLit = distM >= 1850.0 && el > 0.4;

    if (distM < 900.0) {
      featureName = "Shackleton Basin Floor (PSR)";
    } else if (distM <= 2100.0) {
      featureName = "Shackleton Inner Scarp Wall";
    } else if (Math.abs(xM - (-2200)) < 900 && Math.abs(yM) < 3000) {
      featureName = "Connecting Ridge Spine";
    } else {
      featureName = "South Polar Highlands";
    }

    if (distM > 1200 && distM < 2000 && Math.random() > 0.6) {
      mlHazard = true;
      mlConf = 0.82;
    }
  } else {
    xM = (lon / 180.0) * 5450000.0;
    yM = (lat / 90.0) * 2725000.0;
    aspect = (lon + 360) % 360;

    const inProcellarum = lat > -15 && lat < 55 && lon > -80 && lon < -15;
    const inImbrium = lat > 15 && lat < 50 && lon > -40 && lon < 0;
    const inTranquillitatis = lat > -5 && lat < 20 && lon > 15 && lon < 45;
    const inSerenitatis = lat > 15 && lat < 40 && lon > 10 && lon < 35;
    const inSPABasin = lat < -30 && (lon > 140 || lon < -140);
    const nearTycho = Math.hypot(lat - (-43.3), lon - (-11.2)) < 8;
    const nearCopernicus = Math.hypot(lat - 9.6, lon - (-20.1)) < 6;

    if (inProcellarum) {
      elev = -2100;
      slope = 2.1;
      roughness = 0.22;
      featureName = "Oceanus Procellarum (Basalt)";
    } else if (inImbrium) {
      elev = -2600;
      slope = 2.4;
      roughness = 0.28;
      featureName = "Mare Imbrium Basin";
    } else if (inTranquillitatis) {
      elev = -1400;
      slope = 1.8;
      roughness = 0.19;
      featureName = "Mare Tranquillitatis";
    } else if (inSerenitatis) {
      elev = -2200;
      slope = 2.2;
      roughness = 0.24;
      featureName = "Mare Serenitatis";
    } else if (inSPABasin) {
      elev = -6500;
      slope = 4.8;
      roughness = 0.75;
      featureName = "South Pole-Aitken (SPA) Basin";
    } else if (nearTycho) {
      elev = 1400;
      slope = 28.5;
      roughness = 1.95;
      featureName = "Tycho Crater Rim / Ray System";
      mlHazard = true;
      mlConf = 0.94;
    } else if (nearCopernicus) {
      elev = 900;
      slope = 26.2;
      roughness = 1.82;
      featureName = "Copernicus Crater Complex";
      mlHazard = true;
      mlConf = 0.91;
    } else {
      elev = 800 + Math.sin(lat * 0.1) * 600;
      slope = 5.4 + Math.abs(Math.sin(lon * 0.2)) * 3.2;
      roughness = 0.52;
      featureName = lat > 0 ? "Northern Cratered Highlands" : "Southern Lunar Highlands";
    }

    earthVis = lon >= -88.0 && lon <= 88.0;
    const sunLon = (step * 7.5) % 360 - 180;
    const dLon = Math.abs(lon - sunLon);
    const sunAngleDiff = Math.min(dLon, 360 - dLon);
    isLit = sunAngleDiff < 88.0;
  }

  const isTerrainHazard = slope > maxSlopeLimit;
  const isFusedHazard = isTerrainHazard || mlHazard;
  const sunSeries = Array.from({ length: 48 }, (_, t) => {
    if (isSouthPoleRegion) return !isPSR && (t % 4 !== 0);
    const sLon = (t * 7.5) % 360 - 180;
    const diff = Math.min(Math.abs(lon - sLon), 360 - Math.abs(lon - sLon));
    return diff < 88.0;
  });
  const earthSeries = Array.from({ length: 48 }, () => earthVis);
  const litCount = sunSeries.filter(Boolean).length;
  const litFrac = litCount / 48.0;

  return {
    x_m: Math.round(xM),
    y_m: Math.round(yM),
    lat_deg: Math.round(lat * 1000) / 1000,
    lon_deg: Math.round(lon * 10) / 10,
    elevation_m: Math.round(elev * 10) / 10,
    slope_deg: Math.round(slope * 10) / 10,
    aspect_deg: Math.round(aspect * 10) / 10,
    roughness_m: Math.round(roughness * 100) / 100,
    is_hazard: isTerrainHazard,
    feature_name: featureName,
    is_lit: isLit,
    lit_fraction: litFrac,
    longest_dark_hours: isPSR ? 708.0 : (1.0 - litFrac) * 48.0,
    is_psr: isPSR,
    time_series: sunSeries,
    earth_visible: earthVis,
    earth_elevation_deg: earthVis ? 4.2 : -5.0,
    earth_visible_fraction: earthVis ? 0.95 : 0.0,
    longest_blackout_hours: earthVis ? 12.0 : 708.0,
    earth_series: earthSeries,
    ml_hazard_detected: mlHazard,
    ml_confidence: mlConf,
    fused_hazard: isFusedHazard,
  };
}

// Generate realistic procedural lunar surface texture and bump map on an HTML canvas
function createLunarTextures(): { diffuse: THREE.CanvasTexture; bump: THREE.CanvasTexture } {
  const width = 2048;
  const height = 1024;

  const diffCanvas = document.createElement("canvas");
  diffCanvas.width = width;
  diffCanvas.height = height;
  const diffCtx = diffCanvas.getContext("2d")!;

  const bumpCanvas = document.createElement("canvas");
  bumpCanvas.width = width;
  bumpCanvas.height = height;
  const bumpCtx = bumpCanvas.getContext("2d")!;

  // 1. Base Regolith Grey Background (anorthositic highlands)
  diffCtx.fillStyle = "#828489";
  diffCtx.fillRect(0, 0, width, height);
  bumpCtx.fillStyle = "#808080";
  bumpCtx.fillRect(0, 0, width, height);

  // 2. Add fine regolith noise
  const imgData = diffCtx.getImageData(0, 0, width, height);
  const bumpData = bumpCtx.getImageData(0, 0, width, height);
  const dPix = imgData.data;
  const bPix = bumpData.data;

  // Simple deterministic pseudorandom noise for regolith grain
  let seed = 1234567;
  const rnd = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };

  for (let i = 0; i < dPix.length; i += 4) {
    const n = (rnd() - 0.5) * 22;
    dPix[i] = Math.max(0, Math.min(255, dPix[i] + n));
    dPix[i + 1] = Math.max(0, Math.min(255, dPix[i + 1] + n));
    dPix[i + 2] = Math.max(0, Math.min(255, dPix[i + 2] + n));

    bPix[i] = Math.max(0, Math.min(255, bPix[i] + n * 0.8));
    bPix[i + 1] = bPix[i];
    bPix[i + 2] = bPix[i];
  }
  diffCtx.putImageData(imgData, 0, 0);
  bumpCtx.putImageData(bumpData, 0, 0);

  // Helper to draw realistic basaltic Maria
  const drawMare = (cx: number, cy: number, rx: number, ry: number, opacity: number) => {
    // Diffuse: Dark basalt
    const grad = diffCtx.createRadialGradient(cx, cy, 0, cx, cy, rx);
    grad.addColorStop(0, `rgba(45, 48, 54, ${opacity})`);
    grad.addColorStop(0.7, `rgba(55, 58, 65, ${opacity * 0.8})`);
    grad.addColorStop(1, "rgba(130, 132, 137, 0)");

    diffCtx.fillStyle = grad;
    diffCtx.beginPath();
    diffCtx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    diffCtx.fill();

    // Bump: Smooth lower basin
    const bGrad = bumpCtx.createRadialGradient(cx, cy, 0, cx, cy, rx);
    bGrad.addColorStop(0, "rgba(50, 50, 50, 0.7)");
    bGrad.addColorStop(0.8, "rgba(80, 80, 80, 0.3)");
    bGrad.addColorStop(1, "rgba(128, 128, 128, 0)");
    bumpCtx.fillStyle = bGrad;
    bumpCtx.beginPath();
    bumpCtx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    bumpCtx.fill();
  };

  // Nearside Lunar Maria (lat/lon to UV canvas pixels)
  // Oceanus Procellarum & Mare Imbrium
  drawMare(width * 0.38, height * 0.38, 220, 180, 0.85);
  // Mare Imbrium
  drawMare(width * 0.44, height * 0.32, 140, 120, 0.9);
  // Mare Serenitatis
  drawMare(width * 0.53, height * 0.34, 110, 100, 0.88);
  // Mare Tranquillitatis
  drawMare(width * 0.57, height * 0.44, 120, 95, 0.85);
  // Mare Crisium
  drawMare(width * 0.66, height * 0.40, 80, 70, 0.92);
  // Mare Fecunditatis & Nectaris
  drawMare(width * 0.62, height * 0.55, 90, 80, 0.8);
  drawMare(width * 0.58, height * 0.58, 65, 55, 0.82);
  // Mare Nubium & Humorum
  drawMare(width * 0.45, height * 0.58, 100, 80, 0.85);
  drawMare(width * 0.37, height * 0.60, 60, 55, 0.88);

  // South Pole-Aitken Basin (Huge dark depression on farside southern hemisphere)
  drawMare(width * 0.95, height * 0.82, 280, 160, 0.75);
  drawMare(width * 0.05, height * 0.82, 280, 160, 0.75);

  // Helper to draw Impact Craters with bright ejecta rays
  const drawImpactCrater = (cx: number, cy: number, r: number, rayLength: number, rayCount: number) => {
    // Ejecta rays
    if (rayLength > 0) {
      diffCtx.save();
      diffCtx.strokeStyle = "rgba(225, 230, 240, 0.35)";
      diffCtx.lineWidth = 1.8;
      for (let a = 0; a < rayCount; a++) {
        const ang = (a / rayCount) * Math.PI * 2 + rnd() * 0.2;
        const len = rayLength * (0.6 + rnd() * 0.8);
        diffCtx.beginPath();
        diffCtx.moveTo(cx, cy);
        diffCtx.lineTo(cx + Math.cos(ang) * len, cy + Math.sin(ang) * len);
        diffCtx.stroke();
      }
      diffCtx.restore();
    }

    // Crater Rim (bright)
    diffCtx.beginPath();
    diffCtx.arc(cx, cy, r, 0, Math.PI * 2);
    diffCtx.fillStyle = "rgba(235, 240, 250, 0.85)";
    diffCtx.fill();

    // Crater Floor (shadowed bowl)
    diffCtx.beginPath();
    diffCtx.arc(cx, cy, r * 0.75, 0, Math.PI * 2);
    diffCtx.fillStyle = "rgba(50, 52, 58, 0.9)";
    diffCtx.fill();

    // Bump Map: Elevated rim and depressed floor
    bumpCtx.beginPath();
    bumpCtx.arc(cx, cy, r, 0, Math.PI * 2);
    bumpCtx.fillStyle = "rgba(255, 255, 255, 0.9)";
    bumpCtx.fill();

    bumpCtx.beginPath();
    bumpCtx.arc(cx, cy, r * 0.75, 0, Math.PI * 2);
    bumpCtx.fillStyle = "rgba(10, 10, 10, 0.95)";
    bumpCtx.fill();
  };

  // Tycho Crater with prominent rays (Southern highlands)
  drawImpactCrater(width * 0.46, height * 0.72, 18, 280, 24);
  // Copernicus Crater (Equatorial bright rays)
  drawImpactCrater(width * 0.42, height * 0.42, 22, 190, 18);
  // Kepler Crater
  drawImpactCrater(width * 0.35, height * 0.44, 12, 120, 14);
  // Aristarchus Crater (Extremely bright peak)
  drawImpactCrater(width * 0.32, height * 0.36, 14, 110, 12);

  // South Pole (Shackleton & surrounding rim craters)
  drawImpactCrater(width * 0.50, height * 0.97, 10, 60, 12);
  drawImpactCrater(width * 0.48, height * 0.96, 7, 40, 8);
  drawImpactCrater(width * 0.52, height * 0.98, 8, 45, 8);

  // Random scatter of secondary craters
  for (let c = 0; c < 120; c++) {
    const rx = rnd() * width;
    const ry = rnd() * height;
    const rad = 2 + rnd() * 6;
    drawImpactCrater(rx, ry, rad, rad * 3, 6);
  }

  const diffuse = new THREE.CanvasTexture(diffCanvas);
  const bump = new THREE.CanvasTexture(bumpCanvas);
  diffuse.colorSpace = THREE.SRGBColorSpace;
  return { diffuse, bump };
}

export const Moon3DView: React.FC<Moon3DViewProps> = ({ step, onToggle2D, onInspect, layers }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [selectedLandmark, setSelectedLandmark] = useState<Landmark | null>(LUNAR_LANDMARKS[0]);
  const [pinnedInspection, setPinnedInspection] = useState<PointInspection | null>(null);
  const [autoRotate, setAutoRotate] = useState<boolean>(true);
  const [showLandmarks, setShowLandmarks] = useState<boolean>(true);
  const [cameraDistance, setCameraDistance] = useState<number>(3.8);

  const [internalStep, setInternalStep] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const currentStep = step !== undefined ? step : internalStep;

  const togglePlay = () => setIsPlaying((p) => !p);

  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setInternalStep((s) => (s + 1) % 48);
    }, 700);
    return () => clearInterval(interval);
  }, [isPlaying]);

  // Three.js instances ref
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const moonMeshRef = useRef<THREE.Mesh | null>(null);
  const moonMatRef = useRef<THREE.MeshStandardMaterial | null>(null);
  const layerMeshRef = useRef<THREE.Mesh | null>(null);
  const layerCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const layerTextureRef = useRef<THREE.CanvasTexture | null>(null);
  const sampleCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const sunLightRef = useRef<THREE.DirectionalLight | null>(null);
  const markersGroupRef = useRef<THREE.Group | null>(null);
  const mlHazardGroupRef = useRef<THREE.Group | null>(null);
  const psrMarkersGroupRef = useRef<THREE.Group | null>(null);
  const route3DGroupRef = useRef<THREE.Group | null>(null);
  const pinnedMarkerGroupRef = useRef<THREE.Group | null>(null);

  // Orbit state
  const isDraggingRef = useRef<boolean>(false);
  const prevMouseRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const mouseDownPosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const sphericalRef = useRef<{ radius: number; theta: number; phi: number }>({
    radius: 3.8,
    theta: Math.PI * 0.5,
    phi: Math.PI * 0.85, // Angled toward South Pole by default
  });
  const targetLookAtRef = useRef<THREE.Vector3>(new THREE.Vector3(0, 0, 0));

  // Initialize Three.js Scene
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 880;
    const height = container.clientHeight || 600;

    // 1. Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(0x030712); // Deep space slate-950

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    cameraRef.current = camera;
    const { radius, theta, phi } = sphericalRef.current;
    camera.position.setFromSphericalCoords(radius, phi, theta);
    camera.lookAt(0, 0, 0);

    // 3. WebGL Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    rendererRef.current = renderer;
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    // 4. Moon Sphere
    const { diffuse, bump } = createLunarTextures();
    const moonGeo = new THREE.SphereGeometry(1.0, 96, 96);
    const moonMat = new THREE.MeshStandardMaterial({
      map: diffuse,
      bumpMap: bump,
      bumpScale: 0.045,
      roughness: 0.92,
      metalness: 0.05,
    });
    const moonMesh = new THREE.Mesh(moonGeo, moonMat);
    moonMeshRef.current = moonMesh;
    moonMatRef.current = moonMat;
    scene.add(moonMesh);

    // 4b. GIS Layer Overlay Sphere (radius 1.002 to prevent z-fighting with the base Moon sphere)
    const layerCanvas = document.createElement("canvas");
    layerCanvas.width = 1024;
    layerCanvas.height = 512;
    layerCanvasRef.current = layerCanvas;
    const layerTexture = new THREE.CanvasTexture(layerCanvas);
    layerTextureRef.current = layerTexture;

    const layerGeo = new THREE.SphereGeometry(1.002, 96, 96);
    const layerMat = new THREE.MeshBasicMaterial({
      map: layerTexture,
      transparent: true,
      opacity: 0.85,
      depthWrite: false,
    });
    const layerMesh = new THREE.Mesh(layerGeo, layerMat);
    layerMesh.visible = false;
    layerMeshRef.current = layerMesh;
    scene.add(layerMesh);

    // 4c. 3D ML Hazard Beacons Group (Crater Alpha, Beta, Gamma, Delta)
    const mlHazardGroup = new THREE.Group();
    mlHazardGroupRef.current = mlHazardGroup;
    mlHazardGroup.visible = false;
    scene.add(mlHazardGroup);

    SIMULATED_ML_CRATERS.forEach((c) => {
      const { lat, lon } = polarStereoToLatLon(c.x, c.y);
      const pos = latLonToVector3(lat, lon, 1.006);
      const norm = pos.clone().normalize();

      const ringGeo = new THREE.RingGeometry(0.012, 0.02, 24);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0xd946ef,
        transparent: true,
        opacity: 0.9,
        side: THREE.DoubleSide,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.copy(pos.clone().multiplyScalar(1.001));
      ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), norm);

      const stemGeo = new THREE.CylinderGeometry(0.002, 0.002, 0.06, 12);
      const stemMat = new THREE.MeshBasicMaterial({ color: 0xd946ef });
      const stem = new THREE.Mesh(stemGeo, stemMat);
      stem.position.copy(pos.clone().add(norm.clone().multiplyScalar(0.03)));
      stem.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), norm);

      const tipGeo = new THREE.OctahedronGeometry(0.012);
      const tipMat = new THREE.MeshBasicMaterial({ color: 0xf0abfc });
      const tip = new THREE.Mesh(tipGeo, tipMat);
      tip.position.copy(pos.clone().add(norm.clone().multiplyScalar(0.06)));

      mlHazardGroup.add(ring);
      mlHazardGroup.add(stem);
      mlHazardGroup.add(tip);
    });

    // 4d. 3D Cryogenic PSR Cold Trap Beacons Group
    const psrMarkersGroup = new THREE.Group();
    psrMarkersGroupRef.current = psrMarkersGroup;
    psrMarkersGroup.visible = false;
    scene.add(psrMarkersGroup);

    const psrPos = latLonToVector3(-89.9, 0.0, 1.004);
    const psrNorm = psrPos.clone().normalize();
    const psrRingGeo = new THREE.RingGeometry(0.022, 0.032, 32);
    const psrRingMat = new THREE.MeshBasicMaterial({
      color: 0x818cf8,
      transparent: true,
      opacity: 0.85,
      side: THREE.DoubleSide,
    });
    const psrRing = new THREE.Mesh(psrRingGeo, psrRingMat);
    psrRing.position.copy(psrPos);
    psrRing.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), psrNorm);
    psrMarkersGroup.add(psrRing);

    // 4e. 3D Rover Traverse Line & Waypoints
    const route3DGroup = new THREE.Group();
    route3DGroupRef.current = route3DGroup;
    scene.add(route3DGroup);

    const routePoints: THREE.Vector3[] = [];
    MISSION_WAYPOINTS.forEach((wp) => {
      const { lat, lon } = polarStereoToLatLon(wp.x, wp.y);
      const wpPos = latLonToVector3(lat, lon, 1.004);
      routePoints.push(wpPos);

      const wpRingGeo = new THREE.RingGeometry(0.008, 0.014, 16);
      const wpRingMat = new THREE.MeshBasicMaterial({
        color: wp.type === "start" ? 0x10b981 : wp.type === "target" ? 0xf59e0b : 0x38bdf8,
        side: THREE.DoubleSide,
      });
      const wpRing = new THREE.Mesh(wpRingGeo, wpRingMat);
      wpRing.position.copy(wpPos);
      wpRing.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), wpPos.clone().normalize());
      route3DGroup.add(wpRing);
    });

    if (routePoints.length >= 2) {
      const curve = new THREE.CatmullRomCurve3(routePoints);
      const curvePts = curve.getPoints(40);
      const lineGeo = new THREE.BufferGeometry().setFromPoints(curvePts);
      const lineMat = new THREE.LineBasicMaterial({
        color: 0x38bdf8,
        transparent: true,
        opacity: 0.85,
      });
      const routeLine = new THREE.Line(lineGeo, lineMat);
      route3DGroup.add(routeLine);
    }

    // 5. Deep Space Starfield
    const starGeo = new THREE.BufferGeometry();
    const starCount = 1200;
    const starPos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);
      const r = 40 + Math.random() * 20;
      starPos[i] = r * Math.sin(phi) * Math.cos(theta);
      starPos[i + 1] = r * Math.sin(phi) * Math.sin(theta);
      starPos[i + 2] = r * Math.cos(phi);
    }
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({
      color: 0xe2e8f0,
      size: 0.25,
      transparent: true,
      opacity: 0.8,
    });
    const starField = new THREE.Points(starGeo, starMat);
    scene.add(starField);

    // 6. Realistic Lunar Lighting
    // Directional Sun Light (Grazing polar illumination)
    const sunLight = new THREE.DirectionalLight(0xfffaed, 2.8);
    sunLight.position.set(5, 0.4, 5);
    sunLightRef.current = sunLight;
    scene.add(sunLight);

    // Ambient Earthshine & Deep-Space Starlight
    const ambientLight = new THREE.AmbientLight(0x182438, 0.22);
    scene.add(ambientLight);

    // Subtle atmospheric / limb glow ring around Moon
    const limbRingGeo = new THREE.RingGeometry(1.002, 1.018, 64);
    const limbRingMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.18,
      side: THREE.DoubleSide,
    });
    const limbRing = new THREE.Mesh(limbRingGeo, limbRingMat);
    scene.add(limbRing);

    // 7. Landmark Markers Group
    const markersGroup = new THREE.Group();
    markersGroupRef.current = markersGroup;
    scene.add(markersGroup);

    // Create 3D Beacon Rings for each Landmark
    LUNAR_LANDMARKS.forEach((lm) => {
      const pos = latLonToVector3(lm.lat, lm.lon, 1.006);

      // Pin stem
      const stemGeo = new THREE.CylinderGeometry(0.003, 0.003, 0.08, 16);
      const isSouthPole = lm.id === "shackleton";
      const stemMat = new THREE.MeshBasicMaterial({
        color: isSouthPole ? 0x38bdf8 : lm.category === "artemis" ? 0x10b981 : 0xf59e0b,
      });
      const stem = new THREE.Mesh(stemGeo, stemMat);

      // Align cylinder with surface normal
      stem.position.copy(pos);
      stem.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), pos.clone().normalize());

      // Glowing tip beacon
      const tipGeo = new THREE.SphereGeometry(isSouthPole ? 0.022 : 0.015, 16, 16);
      const tipMat = new THREE.MeshBasicMaterial({
        color: isSouthPole ? 0x38bdf8 : lm.category === "artemis" ? 0x34d399 : 0xfbbf24,
      });
      const tip = new THREE.Mesh(tipGeo, tipMat);
      tip.position.copy(pos.clone().add(pos.clone().normalize().multiplyScalar(0.04)));

      // Ground beacon ring
      const ringGeo = new THREE.RingGeometry(0.018, 0.025, 32);
      const ringMat = new THREE.MeshBasicMaterial({
        color: isSouthPole ? 0x38bdf8 : 0x10b981,
        transparent: true,
        opacity: 0.8,
        side: THREE.DoubleSide,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.copy(pos.clone().multiplyScalar(1.002));
      ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), pos.clone().normalize());

      markersGroup.add(stem);
      markersGroup.add(tip);
      markersGroup.add(ring);
    });

    // 8. Animation & Render Loop
    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);

      // Gentle auto-rotation if enabled
      if (autoRotate && !isDraggingRef.current) {
        sphericalRef.current.theta += 0.0018;
      }

      // Update camera position
      const s = sphericalRef.current;
      camera.position.setFromSphericalCoords(s.radius, s.phi, s.theta);
      camera.lookAt(targetLookAtRef.current);

      // Align limb glow with camera
      limbRing.quaternion.copy(camera.quaternion);

      renderer.render(scene, camera);
    };
    animate();

    // Resize handler
    const handleResize = () => {
      if (!container || !renderer || !camera) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    // Native non-passive wheel listener: completely isolates 3D zoom from page scrolling
    const handleNativeWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const zoomDelta = e.deltaY * 0.0025;
      const newRad = Math.max(1.5, Math.min(6.5, sphericalRef.current.radius + zoomDelta));
      sphericalRef.current.radius = newRad;
      setCameraDistance(Number(newRad.toFixed(1)));
    };
    container.addEventListener("wheel", handleNativeWheel, { passive: false });

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
      container.removeEventListener("wheel", handleNativeWheel);
      renderer.dispose();
      moonGeo.dispose();
      moonMat.dispose();
      layerGeo.dispose();
      layerMat.dispose();
      starGeo.dispose();
      starMat.dispose();
      container.innerHTML = "";
    };
  }, []);

  // Synchronize Solar Light Vector with Timeline Step and Illumination Layer
  useEffect(() => {
    if (!sunLightRef.current) return;
    const az = (currentStep * 5.0) % 360.0;
    const el = 1.8 * Math.sin((currentStep / 48) * 2 * Math.PI + 0.3) + 1.2;

    const azRad = (az * Math.PI) / 180;
    const elRad = (el * Math.PI) / 180;

    // Place sun light in orbit
    const sunDist = 7.0;
    const sx = sunDist * Math.cos(elRad) * Math.sin(azRad);
    const sz = sunDist * Math.cos(elRad) * Math.cos(azRad);
    const sy = sunDist * Math.sin(elRad);

    sunLightRef.current.position.set(sx, sy, sz);
    if (layers?.showIllumination) {
      sunLightRef.current.intensity = 3.6;
    } else {
      sunLightRef.current.intensity = 2.8;
    }
  }, [currentStep, layers?.showIllumination]);

  // Dynamic 3D GIS Layers Render Engine
  useEffect(() => {
    if (!layerCanvasRef.current || !layerTextureRef.current || !layerMeshRef.current) return;

    const layerCanvas = layerCanvasRef.current;
    const layerTexture = layerTextureRef.current;
    const layerMesh = layerMeshRef.current;
    const layerCtx = layerCanvas.getContext("2d");
    if (!layerCtx) return;

    const width = layerCanvas.width;
    const height = layerCanvas.height;

    // Check if any GIS layer is active
    const hasActiveLayers =
      layers &&
      (layers.showSlope ||
        layers.showRoughness ||
        layers.showHazard ||
        layers.showPSR ||
        layers.showEarthVisibility ||
        layers.showMLHazard ||
        layers.showFusedHazard ||
        layers.showIllumination ||
        layers.showAspect);

    // Toggle 3D marker groups
    if (mlHazardGroupRef.current) {
      mlHazardGroupRef.current.visible = !!(layers?.showMLHazard || layers?.showFusedHazard);
    }
    if (psrMarkersGroupRef.current) {
      psrMarkersGroupRef.current.visible = !!layers?.showPSR;
    }

    // Toggle topographic relief enhancement for DEM Hillshade
    if (moonMatRef.current) {
      moonMatRef.current.bumpScale = layers?.showHillshade ? 0.08 : 0.025;
    }

    // If no layers are active, hide the layer overlay and clear
    if (!hasActiveLayers) {
      layerMesh.visible = false;
      layerCtx.clearRect(0, 0, width, height);
      layerTexture.needsUpdate = true;
      return;
    }

    // Show the layer overlay
    layerMesh.visible = true;

    // Fast Grid Sampling (256x128) for full-sphere thematic GIS rasters
    const sw = 256;
    const sh = 128;
    if (!sampleCanvasRef.current) {
      sampleCanvasRef.current = document.createElement("canvas");
      sampleCanvasRef.current.width = sw;
      sampleCanvasRef.current.height = sh;
    }
    const sCanvas = sampleCanvasRef.current;
    const sCtx = sCanvas.getContext("2d");
    if (!sCtx) return;

    const sImgData = sCtx.createImageData(sw, sh);
    const sData = sImgData.data;

    const maxSlopeLimit = layers?.maxSlopeLimit ?? 15;
    const colormap = layers?.colormap ?? "viridis";
    const sunLon = (currentStep * 7.5) % 360 - 180;

    for (let py = 0; py < sh; py++) {
      const v = py / sh;
      const lat = (0.5 - v) * 180.0;
      const isSP = lat <= -78.0;

      for (let px = 0; px < sw; px++) {
        const u = px / sw;
        const lon = (u - 0.5) * 360.0;

        let slope = 0;
        let roughness = 0;
        let isPSR = false;
        let earthVis = false;
        let isLit = false;
        let isMLHazard = false;

        if (isSP) {
          const colatRad = (90.0 + lat) * (Math.PI / 180.0);
          const lonRad = (lon * Math.PI) / 180.0;
          const rSP_M = 1737400.0 * colatRad;
          const xM = rSP_M * Math.sin(lonRad);
          const yM = -rSP_M * Math.cos(lonRad);
          slope = getShackletonSlope(xM, yM);
          const distM = Math.hypot(xM, yM);
          roughness = Math.min(2.5, (slope / 18.0) * 1.2 + 0.15);
          isPSR = distM < 1850.0;
          earthVis = distM >= 1850.0;
          const el = 1.8 * Math.sin((currentStep / 48) * 2 * Math.PI + 0.3) + 1.2;
          isLit = distM >= 1850.0 && el > 0.4;
          isMLHazard = distM > 1200 && distM < 2100;
        } else {
          const inProcellarum = lat > -15 && lat < 55 && lon > -80 && lon < -15;
          const inImbrium = lat > 15 && lat < 50 && lon > -40 && lon < 0;
          const inTranquillitatis = lat > -5 && lat < 20 && lon > 15 && lon < 45;
          const inSerenitatis = lat > 15 && lat < 40 && lon > 10 && lon < 35;
          const inSPABasin = lat < -30 && (lon > 140 || lon < -140);
          const nearTycho = Math.hypot(lat - (-43.3), lon - (-11.2)) < 9.0;
          const nearCopernicus = Math.hypot(lat - 9.6, lon - (-20.1)) < 7.0;

          if (inProcellarum || inImbrium || inTranquillitatis || inSerenitatis) {
            slope = 2.0;
            roughness = 0.2;
          } else if (inSPABasin) {
            slope = 5.0;
            roughness = 0.7;
          } else if (nearTycho) {
            slope = 30.0;
            roughness = 2.1;
            isMLHazard = true;
          } else if (nearCopernicus) {
            slope = 27.0;
            roughness = 1.9;
            isMLHazard = true;
          } else {
            slope = 6.0 + Math.abs(Math.sin(lon * 0.2)) * 3.5;
            roughness = 0.55;
          }

          earthVis = lon >= -88.0 && lon <= 88.0;
          const dLon = Math.abs(lon - sunLon);
          isLit = Math.min(dLon, 360 - dLon) < 88.0;
        }

        let r = 0, g = 0, b = 0, a = 0;

        // 1. Slope Map Layer
        if (layers?.showSlope) {
          const normSlope = Math.min(1.0, slope / 45.0);
          const [sr, sg, sb] =
            colormap === "magma"
              ? getMagmaColor(normSlope)
              : colormap === "terrain"
              ? getTerrainRampColor(normSlope)
              : getViridisColor(normSlope);
          r = sr; g = sg; b = sb; a = 180;
        }

        // 2. Roughness Layer (TRI)
        if (layers?.showRoughness) {
          const normTRI = Math.min(1.0, roughness / 2.2);
          const [rr, rg, rb] = getRoughnessColor(normTRI);
          if (a === 0) {
            r = rr; g = rg; b = rb; a = 180;
          } else {
            r = (r + rr) >> 1;
            g = (g + rg) >> 1;
            b = (b + rb) >> 1;
          }
        }

        // 3. Aspect Layer
        if (layers?.showAspect) {
          const asp = (lon + 360) % 360;
          const ar = (128 + 120 * Math.sin((asp * Math.PI) / 180)) | 0;
          const ag = (128 + 120 * Math.cos((asp * Math.PI) / 180)) | 0;
          const ab = 200;
          if (a === 0) {
            r = ar; g = ag; b = ab; a = 160;
          } else {
            r = (r + ar) >> 1;
            g = (g + ag) >> 1;
            b = (b + ab) >> 1;
          }
        }

        // 4. Earth Visibility (Line-of-Sight)
        if (layers?.showEarthVisibility) {
          if (earthVis) {
            if (a === 0) {
              r = 6; g = 182; b = 212; a = 135;
            } else {
              r = (r * 0.5 + 6 * 0.5) | 0;
              g = (g * 0.5 + 182 * 0.5) | 0;
              b = (b * 0.5 + 212 * 0.5) | 0;
              a = Math.max(a, 160);
            }
          } else {
            if (a === 0) {
              r = 225; g = 29; b = 72; a = 145;
            } else {
              r = (r * 0.5 + 225 * 0.5) | 0;
              g = (g * 0.5 + 29 * 0.5) | 0;
              b = (b * 0.5 + 72 * 0.5) | 0;
              a = Math.max(a, 175);
            }
          }
        }

        // 5. Illumination Layer
        if (layers?.showIllumination) {
          if (isLit) {
            if (a === 0) {
              r = 251; g = 191; b = 36; a = 120;
            } else {
              r = Math.min(255, (r * 0.65 + 251 * 0.35) | 0);
              g = Math.min(255, (g * 0.65 + 191 * 0.35) | 0);
              b = (b * 0.65 + 36 * 0.35) | 0;
            }
          } else {
            if (a === 0) {
              r = 3; g = 7; b = 18; a = 180;
            } else {
              r = (r * 0.3) | 0;
              g = (g * 0.3) | 0;
              b = (b * 0.4 + 15) | 0;
              a = Math.max(a, 190);
            }
          }
        }

        // 6. Permanent Shadow Region (PSR) Cold Trap
        if (layers?.showPSR && isPSR) {
          r = 99; g = 102; b = 241; a = 225;
        }

        // 7. Hazard Overlays
        const isTerrainHazard = slope > maxSlopeLimit;
        if (layers?.showFusedHazard && (isTerrainHazard || isMLHazard)) {
          r = 245; g = 158; b = 11; a = 230;
        } else if (layers?.showHazard && isTerrainHazard) {
          r = 239; g = 68; b = 68; a = 230;
        } else if (layers?.showMLHazard && isMLHazard) {
          r = 217; g = 70; b = 239; a = 220;
        }

        const idx = (py * sw + px) * 4;
        sData[idx] = r;
        sData[idx + 1] = g;
        sData[idx + 2] = b;
        sData[idx + 3] = a;
      }
    }

    sCtx.putImageData(sImgData, 0, 0);

    // Scale up onto the main layer texture canvas
    layerCtx.clearRect(0, 0, width, height);
    layerCtx.drawImage(sCanvas, 0, 0, width, height);

    // Vector annotations for ML detected craters
    if (layers?.showMLHazard || layers?.showFusedHazard) {
      SIMULATED_ML_CRATERS.forEach((c) => {
        const { lat, lon } = polarStereoToLatLon(c.x, c.y);
        const cx = ((lon / 360.0) + 0.5) * width;
        const cy = (0.5 - (lat / 180.0)) * height;
        layerCtx.save();
        layerCtx.strokeStyle = "#f0abfc";
        layerCtx.lineWidth = 2;
        layerCtx.beginPath();
        layerCtx.arc(cx, cy, 12, 0, Math.PI * 2);
        layerCtx.stroke();
        layerCtx.fillStyle = "rgba(15, 23, 42, 0.85)";
        layerCtx.fillRect(cx - 24, cy - 20, 48, 12);
        layerCtx.fillStyle = "#f5d0fe";
        layerCtx.font = "bold 8px 'JetBrains Mono', monospace";
        layerCtx.fillText(`ML ${(c.conf * 100).toFixed(0)}%`, cx - 18, cy - 11);
        layerCtx.restore();
      });
    }

    layerTexture.needsUpdate = true;
  }, [layers, currentStep]);

  // Toggle Landmarks Visibility
  useEffect(() => {
    if (markersGroupRef.current) {
      markersGroupRef.current.visible = showLandmarks;
    }
  }, [showLandmarks]);

  // Click-to-Inspect raycasting on 3D Moon Surface
  const handleMoonClick = useCallback(
    (e: React.MouseEvent) => {
      const container = mountRef.current;
      const camera = cameraRef.current;
      const moonMesh = moonMeshRef.current;
      const scene = sceneRef.current;
      if (!container || !camera || !moonMesh || !scene) return;

      const rect = container.getBoundingClientRect();
      const mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const mouseY = -(((e.clientY - rect.top) / rect.height) * 2 - 1);

      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(new THREE.Vector2(mouseX, mouseY), camera);
      const intersects = raycaster.intersectObject(moonMesh);

      if (intersects.length > 0) {
        const hit = intersects[0];
        const pt = hit.point;
        const { lat, lon } = vector3ToLatLon(pt, 1.0);

        const inspection = computeLunarInspection(lat, lon, currentStep, layers?.maxSlopeLimit ?? 15.0);
        setPinnedInspection(inspection);
        setSelectedLandmark(null);
        if (onInspect) {
          onInspect(inspection);
        }

        // Create or reposition 3D pinned target marker on the Moon surface
        if (pinnedMarkerGroupRef.current) {
          scene.remove(pinnedMarkerGroupRef.current);
        }

        const markerGroup = new THREE.Group();
        pinnedMarkerGroupRef.current = markerGroup;

        const norm = pt.clone().normalize();
        const pos = norm.clone().multiplyScalar(1.008);

        // Target ring on surface
        const ringGeo = new THREE.RingGeometry(0.022, 0.034, 32);
        const ringMat = new THREE.MeshBasicMaterial({
          color: inspection.is_hazard ? 0xf43f5e : 0x06b6d4,
          transparent: true,
          opacity: 0.9,
          side: THREE.DoubleSide,
        });
        const ringMesh = new THREE.Mesh(ringGeo, ringMat);
        ringMesh.position.copy(pos);
        ringMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), norm);
        markerGroup.add(ringMesh);

        // Inner target crosshair ring
        const crossRingGeo = new THREE.RingGeometry(0.006, 0.012, 16);
        const crossRingMat = new THREE.MeshBasicMaterial({
          color: 0xffffff,
          side: THREE.DoubleSide,
        });
        const crossMesh = new THREE.Mesh(crossRingGeo, crossRingMat);
        crossMesh.position.copy(pos.clone().multiplyScalar(1.001));
        crossMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), norm);
        markerGroup.add(crossMesh);

        // Vertical beacon stem
        const stemGeo = new THREE.CylinderGeometry(0.003, 0.003, 0.12, 16);
        const stemMat = new THREE.MeshBasicMaterial({
          color: inspection.is_hazard ? 0xf43f5e : 0x06b6d4,
        });
        const stemMesh = new THREE.Mesh(stemGeo, stemMat);
        stemMesh.position.copy(pos.clone().add(norm.clone().multiplyScalar(0.06)));
        stemMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), norm);
        markerGroup.add(stemMesh);

        // Glowing beacon tip
        const tipGeo = new THREE.SphereGeometry(0.018, 16, 16);
        const tipMat = new THREE.MeshBasicMaterial({
          color: inspection.is_hazard ? 0xfb7185 : 0x38bdf8,
        });
        const tipMesh = new THREE.Mesh(tipGeo, tipMat);
        tipMesh.position.copy(pos.clone().add(norm.clone().multiplyScalar(0.12)));
        markerGroup.add(tipMesh);

        scene.add(markerGroup);
      }
    },
    [currentStep, layers?.maxSlopeLimit, onInspect]
  );

  const handleUnpin = useCallback(() => {
    setPinnedInspection(null);
    if (sceneRef.current && pinnedMarkerGroupRef.current) {
      sceneRef.current.remove(pinnedMarkerGroupRef.current);
      pinnedMarkerGroupRef.current = null;
    }
    if (onInspect) {
      onInspect(null);
    }
  }, [onInspect]);

  // Mouse & Touch Controls
  const handleMouseDown = (e: React.MouseEvent) => {
    isDraggingRef.current = true;
    prevMouseRef.current = { x: e.clientX, y: e.clientY };
    mouseDownPosRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - prevMouseRef.current.x;
    const dy = e.clientY - prevMouseRef.current.y;
    prevMouseRef.current = { x: e.clientX, y: e.clientY };

    // Update spherical orbit coordinates
    sphericalRef.current.theta -= dx * 0.006;
    sphericalRef.current.phi = Math.max(0.05, Math.min(Math.PI - 0.05, sphericalRef.current.phi - dy * 0.006));
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    isDraggingRef.current = false;
    const moveDist = Math.hypot(
      e.clientX - mouseDownPosRef.current.x,
      e.clientY - mouseDownPosRef.current.y
    );
    if (moveDist < 6) {
      handleMoonClick(e);
    }
  };

  // Quick Camera Presets
  const setCameraPreset = useCallback((preset: "south_pole" | "nearside" | "farside" | "terminator") => {
    setAutoRotate(false);
    if (preset === "south_pole") {
      // Look straight down at South Pole (-89.9°S)
      sphericalRef.current = { radius: 2.3, theta: Math.PI * 0.5, phi: Math.PI * 0.94 };
      setSelectedLandmark(LUNAR_LANDMARKS[0]);
    } else if (preset === "nearside") {
      // Classic Earth-facing view (0° Lat, 0° Lon)
      sphericalRef.current = { radius: 3.2, theta: Math.PI * 0.5, phi: Math.PI * 0.5 };
    } else if (preset === "farside") {
      // Farside & South Pole Aitken Basin
      sphericalRef.current = { radius: 3.2, theta: Math.PI * 1.5, phi: Math.PI * 0.65 };
    } else if (preset === "terminator") {
      // Solar day/night terminator boundary
      sphericalRef.current = { radius: 2.8, theta: 0.0, phi: Math.PI * 0.5 };
    }
    setCameraDistance(Number(sphericalRef.current.radius.toFixed(1)));
  }, []);

  const focusLandmark = (lm: Landmark) => {
    setSelectedLandmark(lm);
    setAutoRotate(false);
    // Smoothly orient camera toward landmark
    const targetVec = latLonToVector3(lm.lat, lm.lon, 1.0);
    const spherical = new THREE.Spherical().setFromVector3(targetVec.multiplyScalar(2.4));
    sphericalRef.current = {
      radius: 2.4,
      theta: spherical.theta,
      phi: Math.max(0.08, Math.min(Math.PI - 0.08, spherical.phi)),
    };
    setCameraDistance(2.4);
  };

  const hasActiveLayers = Boolean(
    layers &&
      (layers.showSlope ||
        layers.showRoughness ||
        layers.showHazard ||
        layers.showPSR ||
        layers.showEarthVisibility ||
        layers.showMLHazard ||
        layers.showFusedHazard ||
        layers.showIllumination ||
        layers.showAspect)
  );

  return (
    <div className="flex flex-col gap-3 w-full" style={{ width: "100%" }}>
      {/* 3D Viewport Container */}
      <div
        className="relative w-full rounded-2xl overflow-hidden border border-white/10 bg-slate-950 shadow-2xl"
        style={{ width: "100%", height: 600, minHeight: 600, position: "relative", overscrollBehavior: "contain" }}
      >
        <div
          ref={mountRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          className="w-full h-full cursor-crosshair"
          style={{ width: "100%", height: "100%", display: "block", touchAction: "none", overscrollBehavior: "contain" }}
          aria-label="Interactive 3D Moon Surface Visualization"
        />

        {/* Top-Left: Telemetry & Orientation HUD */}
        <div className="absolute top-4 left-4 glass-panel px-3.5 py-2.5 flex flex-col gap-1.5 text-[11px] font-mono pointer-events-none select-none z-10 max-w-sm">
          <div className="flex items-center gap-2 text-sky-300 font-bold">
            <Moon className="w-4 h-4 text-sky-400" />
            <span>3D LUNAR GLOBE: HIGH-RESOLUTION VISUALIZER</span>
          </div>
          <div className="flex items-center gap-2 text-emerald-300 text-[10px]">
            <Globe className="w-3.5 h-3.5 text-emerald-400" />
            <span>ORBIT RADIUS: {(cameraDistance * 1737.4).toFixed(0)} KM | ALT: {((cameraDistance - 1) * 1737.4).toFixed(0)} KM</span>
          </div>
          <div className="text-gray-400 flex items-center gap-2 text-[10px]">
            <span>SPHERE: R = 1,737.4 km</span>
            <span>•</span>
            <span className="text-sky-300">SOLAR AZ: {((currentStep * 5.0) % 360).toFixed(1)}°</span>
            <span>•</span>
            <span className="text-amber-300">SIM STEP {currentStep + 1}/48</span>
          </div>

          {/* Active 3D GIS Layers Badges */}
          {hasActiveLayers && (
            <div className="mt-1 pt-1.5 border-t border-white/10 flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-[10px] text-cyan-300 font-semibold uppercase">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                <span>Active 3D GIS Layers</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {layers?.showFusedHazard && (
                  <span className="px-1.5 py-0.5 rounded bg-amber-500/25 border border-amber-500/50 text-amber-200 text-[9px] font-bold">
                    FUSED HAZARD (FR-13)
                  </span>
                )}
                {layers?.showMLHazard && (
                  <span className="px-1.5 py-0.5 rounded bg-fuchsia-500/25 border border-fuchsia-500/50 text-fuchsia-200 text-[9px]">
                    ML CRATERS ({Math.round((layers.mlConfidenceThreshold ?? 0.6) * 100)}%)
                  </span>
                )}
                {layers?.showHazard && (
                  <span className="px-1.5 py-0.5 rounded bg-rose-500/25 border border-rose-500/50 text-rose-200 text-[9px]">
                    SLOPE &gt;{layers.maxSlopeLimit}°
                  </span>
                )}
                {layers?.showSlope && (
                  <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-[9px]">
                    <span>SLOPE ({layers.colormap?.toUpperCase() ?? "VIRIDIS"})</span>
                    <div
                      className={`w-8 h-1 rounded-sm ml-0.5 ${
                        layers.colormap === "magma"
                          ? "bg-gradient-to-r from-black via-purple-600 via-rose-500 to-amber-300"
                          : layers.colormap === "terrain"
                          ? "bg-gradient-to-r from-emerald-500 via-amber-400 to-rose-600"
                          : "bg-gradient-to-r from-indigo-700 via-emerald-500 to-yellow-300"
                      }`}
                    />
                  </div>
                )}
                {layers?.showRoughness && (
                  <span className="px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200 text-[9px]">
                    ROUGHNESS (TRI)
                  </span>
                )}
                {layers?.showPSR && (
                  <span className="px-1.5 py-0.5 rounded bg-indigo-500/25 border border-indigo-500/50 text-indigo-200 text-[9px]">
                    ❄ PSR COLD TRAPS
                  </span>
                )}
                {layers?.showEarthVisibility && (
                  <span className="px-1.5 py-0.5 rounded bg-sky-500/25 border border-sky-500/50 text-sky-200 text-[9px]">
                    EARTH LINE-OF-SIGHT
                  </span>
                )}
                {layers?.showIllumination && (
                  <span className="px-1.5 py-0.5 rounded bg-yellow-500/25 border border-yellow-500/50 text-yellow-200 text-[9px]">
                    SOLAR ILLUMINATION
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Top-Right: Camera Presets & Control Dock */}
        <div className="absolute top-4 right-4 flex flex-col gap-1.5 glass-panel p-2 shadow-xl select-none">
          <div className="text-[10px] font-mono text-gray-400 uppercase tracking-wider mb-1 px-1">Camera Views</div>
          <button
            onClick={() => setCameraPreset("south_pole")}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono bg-sky-500/20 text-sky-300 hover:bg-sky-500/30 border border-sky-500/40 transition-colors"
          >
            <Compass className="w-3.5 h-3.5" />
            <span>South Pole (AOI)</span>
          </button>
          <button
            onClick={() => setCameraPreset("nearside")}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono bg-white/5 text-gray-300 hover:bg-white/10 border border-white/5 transition-colors"
          >
            <Globe className="w-3.5 h-3.5" />
            <span>Earth-Facing</span>
          </button>
          <button
            onClick={() => setCameraPreset("farside")}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono bg-white/5 text-gray-300 hover:bg-white/10 border border-white/5 transition-colors"
          >
            <Navigation className="w-3.5 h-3.5" />
            <span>Farside / SPA</span>
          </button>
          <button
            onClick={() => setCameraPreset("terminator")}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono bg-white/5 text-gray-300 hover:bg-white/10 border border-white/5 transition-colors"
          >
            <Sun className="w-3.5 h-3.5 text-amber-400" />
            <span>Terminator</span>
          </button>

          <div className="h-px bg-white/10 my-1" />

          {/* Toggle Auto-Rotate */}
          <button
            onClick={() => setAutoRotate(!autoRotate)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono transition-colors ${
              autoRotate
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                : "bg-white/5 text-gray-400 hover:bg-white/10"
            }`}
          >
            <RotateCw className={`w-3.5 h-3.5 ${autoRotate ? "animate-spin" : ""}`} />
            <span>Orbit Cam: {autoRotate ? "ON" : "OFF"}</span>
          </button>

          {/* Toggle Landmarks */}
          <button
            onClick={() => setShowLandmarks(!showLandmarks)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono transition-colors ${
              showLandmarks
                ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                : "bg-white/5 text-gray-400 hover:bg-white/10"
            }`}
          >
            <MapPin className="w-3.5 h-3.5" />
            <span>Markers: {showLandmarks ? "ON" : "OFF"}</span>
          </button>

          {onToggle2D && (
            <>
              <div className="h-px bg-white/10 my-1" />
              <button
                onClick={onToggle2D}
                aria-label="Switch to 2D Polar Map"
                title="Switch to 2D Polar Map"
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono bg-sky-500/20 text-sky-300 hover:bg-sky-500/30 border border-sky-500/40 transition-colors"
              >
                <Compass className="w-3.5 h-3.5" />
                <span>2D Polar Map</span>
              </button>
            </>
          )}
        </div>

        {/* Bottom-Left: Pinned Pixel Terrain Inspection or Selected Landmark Card */}
        {pinnedInspection ? (
          <div className="absolute bottom-4 left-4 glass-panel p-3 max-w-sm flex flex-col gap-2 text-xs font-mono border-l-2 border-l-cyan-400 shadow-2xl">
            <div className="flex items-center justify-between">
              <span className="font-bold text-cyan-300 text-sm flex items-center gap-1.5">
                <Target className="w-4 h-4 text-cyan-400" />
                {pinnedInspection.feature_name}
              </span>
              <button
                onClick={handleUnpin}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-white/10 hover:bg-rose-500/20 text-gray-300 hover:text-rose-300 transition-colors text-[10px]"
              >
                <X className="w-3 h-3" />
                <span>UNPIN</span>
              </button>
            </div>

            <div
              className={`flex items-center justify-between p-1.5 rounded border text-[11px] font-sans font-semibold ${
                pinnedInspection.is_hazard
                  ? "bg-rose-950/40 border-rose-500/40 text-rose-300"
                  : "bg-emerald-950/40 border-emerald-500/40 text-emerald-300"
              }`}
            >
              <div className="flex items-center gap-1.5">
                {pinnedInspection.is_hazard ? (
                  <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                ) : (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                )}
                <span>{pinnedInspection.is_hazard ? "SLOPE EXCEEDED" : "SAFE TERRAIN"}</span>
              </div>
              <span className="font-mono text-[10px]">
                {pinnedInspection.slope_deg.toFixed(1)}° (MAX {layers?.maxSlopeLimit ?? 15}°)
              </span>
            </div>

            <div className="text-[10px] text-gray-300 bg-white/5 p-1.5 rounded grid grid-cols-2 gap-1.5">
              <div>
                Coords: <strong className="text-white">{pinnedInspection.lat_deg > 0 ? `${pinnedInspection.lat_deg}°N` : `${Math.abs(pinnedInspection.lat_deg)}°S`}, {pinnedInspection.lon_deg}°E</strong>
              </div>
              <div>
                Elev: <strong className="text-emerald-300">{pinnedInspection.elevation_m} m</strong>
              </div>
              <div>
                Sun: <strong className={pinnedInspection.is_lit ? "text-amber-300" : "text-gray-400"}>{pinnedInspection.is_lit ? "SUNLIT" : "SHADOW"}</strong>
              </div>
              <div>
                Earth LOS: <strong className={pinnedInspection.earth_visible ? "text-sky-300" : "text-rose-400"}>{pinnedInspection.earth_visible ? "VISIBLE" : "OCCULTED"}</strong>
              </div>
            </div>

            <div className="text-[10px] text-cyan-300/80 italic flex items-center justify-between">
              <span>Full telemetry sent to Mission Dock</span>
              <span>•</span>
              <span className="text-gray-400">Click anywhere to inspect</span>
            </div>
          </div>
        ) : selectedLandmark ? (
          <div className="absolute bottom-4 left-4 glass-panel p-3 max-w-sm flex flex-col gap-1.5 text-xs font-mono border-l-2 border-l-sky-400 shadow-2xl">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sky-300 text-sm flex items-center gap-1.5">
                <MapPin className="w-4 h-4 text-sky-400" />
                {selectedLandmark.name}
              </span>
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                  selectedLandmark.category === "artemis"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : selectedLandmark.category === "ridge"
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/30"
                    : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                }`}
              >
                {selectedLandmark.category}
              </span>
            </div>
            <p className="text-gray-300 text-[11px] leading-relaxed">{selectedLandmark.description}</p>
            <div className="text-[10px] text-gray-400 bg-white/5 p-1.5 rounded flex items-center justify-between">
              <span>Coords: {selectedLandmark.lat > 0 ? `${selectedLandmark.lat}°N` : `${Math.abs(selectedLandmark.lat)}°S`}, {selectedLandmark.lon}°E</span>
              <span className="text-sky-300 font-bold">{selectedLandmark.elevM} m</span>
            </div>
            <div className="text-[10px] text-emerald-300/80 italic flex items-center justify-between">
              <span>{selectedLandmark.details}</span>
              <span className="text-cyan-300 font-sans ml-2">(Click Moon to inspect)</span>
            </div>
          </div>
        ) : null}

        {/* Bottom-Right: Interactive Landmark Switcher Chips */}
        <div className="absolute bottom-4 right-4 flex items-center gap-1.5 overflow-x-auto max-w-lg glass-panel p-1.5">
          {LUNAR_LANDMARKS.map((lm) => (
            <button
              key={lm.id}
              onClick={() => focusLandmark(lm)}
              className={`px-2 py-1 rounded text-[11px] font-mono whitespace-nowrap transition-all ${
                selectedLandmark?.id === lm.id
                  ? "bg-sky-500 text-black font-bold shadow-md shadow-sky-500/30"
                  : "bg-white/5 text-gray-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              {lm.name.split(" ")[0]}
            </button>
          ))}
        </div>
      </div>

      {/* Synchronized Solar Timeline Scrubber Bar */}
      <div className="glass-panel p-3 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="px-2.5 py-1.5 rounded-lg bg-sky-500/20 text-sky-300 hover:bg-sky-500/30 border border-sky-500/40 text-xs font-mono flex items-center gap-1.5"
          >
            <span>{isPlaying ? "⏸ PAUSE" : "▶ PLAY"}</span>
          </button>
          <span className="text-xs font-mono text-gray-300">
            SUN PHASE: <strong className="text-white">{(currentStep * 7.5).toFixed(1)}h</strong> ({currentStep + 1}/48)
          </span>
          <input
            type="range"
            min={0}
            max={47}
            value={currentStep}
            onChange={(e) => setInternalStep(Number(e.target.value))}
            className="w-36 h-1.5 accent-sky-400 bg-white/10 rounded cursor-pointer"
            aria-label="Solar Illumination Step"
          />
        </div>

        <div className="flex items-center gap-3 text-xs font-mono text-gray-400">
          <span>Drag with mouse to rotate 360° • Scroll to zoom</span>
          <span className="text-sky-400">3D WebGL (Three.js)</span>
        </div>
      </div>
    </div>
  );
};
