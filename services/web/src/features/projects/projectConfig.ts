export interface MissionWaypoint {
  id: string;
  label: string;
  x: number;
  y: number;
  elev: number;
  type: "start" | "waypoint" | "science" | "target";
}

export interface MissionLandmark {
  id: string;
  name: string;
  category: "artemis" | "apollo" | "psr" | "ridge" | "viper";
  lat: number;
  lon: number;
  elevM: number;
  description: string;
  details: string;
}

export interface ProjectConfig {
  id: string;
  name: string;
  codename: string;
  aoiLabel: string;
  aoiDescription: string;
  centerLat: number;
  centerLon: number;
  centerStereoX: number;
  centerStereoY: number;
  extentM: number;
  targetFeature: string;
  rover: {
    model: string;
    batteryCapacityWh: number;
    nominalSlopeDeg: number;
    maxTraversableSlopeDeg: number;
    driveSpeedMps: number;
    idlePowerW: number;
    drivePowerW: number;
  };
  plannerDefaults: {
    startCoords: [number, number];
    goalCoords: [number, number];
    startLabel: string;
    goalLabel: string;
  };
  waypoints: MissionWaypoint[];
  landmarks: MissionLandmark[];
  elevationProfile: (xM: number, yM: number) => number;
}

export const MISSION_PROJECTS: Record<string, ProjectConfig> = {
  "00000000-0000-0000-0000-000000000001": {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Artemis-3 (Shackleton)",
    codename: "ARTEMIS-III",
    aoiLabel: "SHACKLETON POLAR AOI",
    aoiDescription: "South Pole 89.9°S, 0.0°E • Shackleton Crater Rim & Connecting Ridge Corridor",
    centerLat: -89.9,
    centerLon: 0.0,
    centerStereoX: 0,
    centerStereoY: 0,
    extentM: 10000.0,
    targetFeature: "Shackleton Crater Rim Crest",
    rover: {
      model: "Artemis LTV (Lunar Terrain Vehicle)",
      batteryCapacityWh: 1200,
      nominalSlopeDeg: 15.0,
      maxTraversableSlopeDeg: 20.0,
      driveSpeedMps: 0.25,
      idlePowerW: 15.0,
      drivePowerW: 140.0,
    },
    plannerDefaults: {
      startCoords: [-1.6, 0.0],
      goalCoords: [1.6, 0.0],
      startLabel: "Lander Alpha (Rim South)",
      goalLabel: "Connecting Ridge Peak",
    },
    waypoints: [
      { id: "WP-0", label: "LANDER-ALPHA", x: -2600, y: -800, elev: -790, type: "start" },
      { id: "WP-1", label: "RIDGE-SPINE", x: -2100, y: 300, elev: -840, type: "waypoint" },
      { id: "WP-2", label: "SHACKLETON-CREST", x: -1500, y: 1400, elev: -910, type: "science" },
      { id: "WP-3", label: "PSR-EDGE", x: -600, y: 1750, elev: -1600, type: "target" },
    ],
    landmarks: [
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
        description: "Traversable high-elevation corridor connecting Shackleton and de Gerlache rims.",
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
    ],
    elevationProfile: (xM: number, yM: number) => {
      const dist = Math.hypot(xM, yM);
      const zFloor = -4180.0;
      const zRim = -3300.0;
      const zPlain = -3750.0;
      const rFloor = 850.0;
      const rRim = 2100.0;
      let base: number;
      if (dist <= rFloor) {
        const normR = dist / rFloor;
        base = zFloor + 50.0 * (normR * normR);
      } else if (dist <= rRim) {
        const t = (dist - rFloor) / (rRim - rFloor);
        const s = 3.0 * t * t - 2.0 * t * t * t;
        base = zFloor + 50.0 + (zRim - (zFloor + 50.0)) * s;
      } else {
        const dr = dist - rRim;
        const decay = Math.exp(-Math.pow(dr / 3600.0, 1.25));
        base = zPlain + (zRim - zPlain) * decay;
      }
      const rx = (xM - -2200.0) / 1100.0;
      const ry = yM / 4500.0;
      const ridgeBoost = 180.0 * Math.exp(-(rx * rx + ry * ry));
      return base + ridgeBoost;
    },
  },

  "00000000-0000-0000-0000-000000000002": {
    id: "00000000-0000-0000-0000-000000000002",
    name: "VIPER-Extended (Nobile)",
    codename: "NASA-VIPER",
    aoiLabel: "NOBILE / MONS MOUTON AOI",
    aoiDescription: "South Polar Region 85.2°S, 53.5°E • Mons Mouton Plateau & Nobile Crater Cold Trap",
    centerLat: -85.2,
    centerLon: 53.5,
    centerStereoX: 118500,
    centerStereoY: 86200,
    extentM: 12000.0,
    targetFeature: "Mons Mouton Massif & Nobile Rim",
    rover: {
      model: "VIPER (Volatiles Investigating Polar Rover)",
      batteryCapacityWh: 500,
      nominalSlopeDeg: 12.0,
      maxTraversableSlopeDeg: 15.0,
      driveSpeedMps: 0.10,
      idlePowerW: 5.0,
      drivePowerW: 80.0,
    },
    plannerDefaults: {
      startCoords: [-3.8, -1.5],
      goalCoords: [3.2, 2.1],
      startLabel: "Mons Mouton Landing Site",
      goalLabel: "Nobile Basin PSR Drill Site",
    },
    waypoints: [
      { id: "VIPER-0", label: "VIPER-LANDER", x: -3800, y: -1500, elev: 5400, type: "start" },
      { id: "VIPER-1", label: "COMM-RIDGE", x: -1600, y: -300, elev: 5850, type: "waypoint" },
      { id: "VIPER-2", label: "NOBILE-SCARP", x: 1200, y: 900, elev: 4200, type: "science" },
      { id: "VIPER-3", label: "DRILL-TARGET", x: 3200, y: 2100, elev: -1200, type: "target" },
    ],
    landmarks: [
      {
        id: "mons_mouton",
        name: "Mons Mouton Massif",
        category: "viper",
        lat: -84.6,
        lon: 48.0,
        elevM: 6100,
        description: "Expansive high-elevation lunar plateau receiving prolonged solar illumination.",
        details: "Summit Elevation: +6.1 km | Priority landing site for NASA VIPER mission",
      },
      {
        id: "nobile_crater",
        name: "Nobile Crater",
        category: "psr",
        lat: -85.2,
        lon: 53.5,
        elevM: -1800,
        description: "Large 73-km degraded polar crater harboring extensive sub-surface water ice reserves.",
        details: "Diameter: 73 km | Deep Permanently Shadowed Regions across floor",
      },
      {
        id: "nobile_comms_peak",
        name: "Nobile Comms Ridge",
        category: "ridge",
        lat: -85.5,
        lon: 51.2,
        elevM: 4800,
        description: "High sunlit promontory enabling continuous Earth communications and rover relay.",
        details: "Direct-to-Earth Visibility: 98% during operational periods",
      },
    ],
    elevationProfile: (xM: number, yM: number) => {
      // Mons Mouton plateau on the west (x < 0) transitioning to Nobile Crater basin on the east (x > 0)
      const plateauElev = 5800.0;
      const basinElev = -1800.0;
      // Sigmoid scarp transition across x = 0
      const tx = xM / 2200.0;
      const sig = 1.0 / (1.0 + Math.exp(-tx));
      const baseElev = plateauElev * (1.0 - sig) + basinElev * sig;

      // Local crater depressions and rolling hills
      const hill1 = 350.0 * Math.exp(-((xM + 2500) ** 2 + (yM - 500) ** 2) / (1800 * 1800));
      const craterDent = -900.0 * Math.exp(-((xM - 2800) ** 2 + (yM - 1800) ** 2) / (1400 * 1400));
      return baseElev + hill1 + craterDent;
    },
  },
};

export function getProjectConfig(projectId: string): ProjectConfig {
  return (
    MISSION_PROJECTS[projectId] ||
    MISSION_PROJECTS["00000000-0000-0000-0000-000000000001"]
  );
}
