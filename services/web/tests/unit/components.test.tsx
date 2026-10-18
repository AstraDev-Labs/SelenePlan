import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Banner } from "../../src/components/Banner";
import { Navbar } from "../../src/components/Navbar";
import { LayerControl, LayerState } from "../../src/features/map/LayerControl";
import { InspectorPanel } from "../../src/features/map/InspectorPanel";
import { TimelineScrubber } from "../../src/features/map/TimelineScrubber";
import { PolarMap } from "../../src/features/map/PolarMap";
import { PlannerPanel } from "../../src/features/map/PlannerPanel";
import { Moon3DView } from "../../src/features/map/Moon3DView";
import { MISSION_PROJECTS } from "../../src/features/projects/projectConfig";
import { useAuthStore } from "../../src/auth/store";

describe("Web UI Components", () => {
  it("renders Banner with flight disclaimer and Moon radius", () => {
    render(<Banner />);
    expect(screen.getByText(/Not flight-qualified/i)).toBeInTheDocument();
    expect(screen.getByText(/1,737.4 km/i)).toBeInTheDocument();
  });

  it("renders Navbar with role-aware tabs for Analyst", () => {
    useAuthStore.getState().login("token-analyst", {
      sub: "analyst-1",
      name: "Dr. Analyst",
      email: "a@selene.org",
      roles: ["analyst"],
      projects: ["00000000-0000-0000-0000-000000000001"],
    });

    render(<Navbar activeTab="map" onTabChange={vi.fn()} />);

    expect(screen.getByText("Polar Map")).toBeInTheDocument();
    expect(screen.getByText("3D Moon Globe")).toBeInTheDocument();
    expect(screen.getByText("Scenarios")).toBeInTheDocument();
    // Analyst cannot see Approvals or Datasets tabs
    expect(screen.queryByText("Approvals")).toBeNull();
    expect(screen.queryByText("Datasets")).toBeNull();
  });

  it("renders Navbar with Datasets tab for Steward", () => {
    useAuthStore.getState().login("token-steward", {
      sub: "steward-1",
      name: "Steward",
      email: "s@selene.org",
      roles: ["steward"],
      projects: ["00000000-0000-0000-0000-000000000001"],
    });

    render(<Navbar activeTab="datasets" onTabChange={vi.fn()} />);
    expect(screen.getByText("Datasets")).toBeInTheDocument();
    expect(screen.queryByText("Approvals")).toBeNull();
  });

  it("triggers layer toggles and threshold adjustments in LayerControl", () => {
    const handleChange = vi.fn();
    const initialLayers = {
      showSlope: true,
      showAspect: false,
      showRoughness: false,
      showHazard: true,
      showHillshade: false,
      showIllumination: true,
      showPSR: false,
      showEarthVisibility: false,
      showMLHazard: false,
      showFusedHazard: true,
      mlConfidenceThreshold: 0.60,
      colormap: "viridis" as const,
      maxSlopeLimit: 15,
    };

    render(<LayerControl layers={initialLayers} onChange={handleChange} />);

    // Verify model info card and advisory warning
    expect(screen.getByText(/crater_detector_v1/i)).toBeInTheDocument();
    expect(screen.getByText(/ML crater detections are advisory/i)).toBeInTheDocument();

    // Click slope toggle
    const slopeBtn = screen.getByText(/Slope \(Horn 3x3\)/i);
    fireEvent.click(slopeBtn);
    expect(handleChange).toHaveBeenCalledWith(
      expect.objectContaining({ showSlope: false })
    );

    // Toggle Fused Hazard
    const fusedBtn = screen.getByText(/Fused Hazard Map/i);
    fireEvent.click(fusedBtn);
    expect(handleChange).toHaveBeenCalledWith(
      expect.objectContaining({ showFusedHazard: false })
    );

    // Change colormap
    const select = screen.getByLabelText(/Slope Colormap/i);
    fireEvent.change(select, { target: { value: "magma" } });
    expect(handleChange).toHaveBeenCalledWith(
      expect.objectContaining({ colormap: "magma" })
    );
  });

  it("displays formatted telemetry in InspectorPanel", () => {
    const inspection = {
      x_m: 1200.5,
      y_m: -3400.2,
      lat_deg: 89.88,
      lon_deg: 160.5,
      elevation_m: -1850.4,
      slope_deg: 24.3,
      aspect_deg: 135.0,
      roughness_m: 1.94,
      is_hazard: true,
      feature_name: "Shackleton Inner Wall",
      ml_hazard_detected: true,
      ml_confidence: 0.85,
      fused_hazard: true,
    };

    render(<InspectorPanel inspection={inspection} />);
    expect(screen.getByText("Shackleton Inner Wall")).toBeInTheDocument();
    expect(screen.getByText("-1850.4 m")).toBeInTheDocument();
    expect(screen.getByText("24.3°")).toBeInTheDocument();
    expect(screen.getByText("FUSED HAZARD")).toBeInTheDocument();
    expect(screen.getByText("SLOPE EXCEEDED")).toBeInTheDocument();
    expect(screen.getByText(/ML Crater Detector/i)).toBeInTheDocument();
    expect(screen.getByText(/85% CONF/i)).toBeInTheDocument();
  });

  it("displays SAFE TERRAIN and TRAVERSABLE badge when slope is within safe limits", () => {
    const safeInspection = {
      x_m: -2200.0,
      y_m: 500.0,
      lat_deg: 89.92,
      lon_deg: 135.0,
      elevation_m: -3120.0,
      slope_deg: 4.8,
      aspect_deg: 45.0,
      roughness_m: 0.42,
      is_hazard: false,
      feature_name: "Connecting Ridge Spine",
      ml_hazard_detected: false,
      ml_confidence: 0.0,
      fused_hazard: false,
    };

    render(<InspectorPanel inspection={safeInspection} />);
    expect(screen.getByText("Connecting Ridge Spine")).toBeInTheDocument();
    expect(screen.getByText("SAFE TERRAIN")).toBeInTheDocument();
    expect(screen.getByText("TRAVERSABLE")).toBeInTheDocument();
    expect(screen.getByText("4.8°")).toBeInTheDocument();
    expect(screen.getByText("CLEAR")).toBeInTheDocument();
  });

  it("handles playback, scrubbing, and speed changes in TimelineScrubber", () => {
    const handleStep = vi.fn();
    const timestamps = ["2026-03-01T00:00:00Z", "2026-03-01T01:00:00Z", "2026-03-01T02:00:00Z"];

    render(
      <TimelineScrubber
        totalSteps={3}
        currentStep={1}
        onStepChange={handleStep}
        timestamps={timestamps}
        litFraction={0.75}
      />
    );

    // Verify telemetry
    expect(screen.getByText("2026-03-01T01:00:00Z")).toBeInTheDocument();
    expect(screen.getByText("75.0%")).toBeInTheDocument();

    // Toggle play button
    const playBtn = screen.getByRole("button", { name: /Play Timeline Playback/i });
    fireEvent.click(playBtn);
    expect(screen.getByRole("button", { name: /Pause Timeline Playback/i })).toBeInTheDocument();

    // Change speed
    const speed5x = screen.getByRole("button", { name: /Set playback speed 5x/i });
    fireEvent.click(speed5x);
    expect(speed5x).toHaveClass("bg-cyan-500/30");

    // Scrubber slider change
    const slider = screen.getByLabelText(/Timeline Scrubber Slider/i);
    fireEvent.change(slider, { target: { value: "2" } });
    expect(handleStep).toHaveBeenCalledWith(2);
  });

  it("renders Moon3DView with telemetry HUD, camera presets, and landmark markers", () => {
    const handleInspect = vi.fn();
    render(<Moon3DView onInspect={handleInspect} />);

    expect(screen.getByText(/3D LUNAR GLOBE/i)).toBeInTheDocument();
    expect(screen.getByText(/South Pole \(AOI\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Earth-Facing/i)).toBeInTheDocument();
    expect(screen.getByText(/Shackleton Crater/i)).toBeInTheDocument();
  });

  it("renders Moon3DView with active 3D GIS layers and colormap indicators", () => {
    const layers: LayerState = {
      showSlope: true,
      showAspect: false,
      showRoughness: true,
      showHazard: true,
      showHillshade: true,
      showIllumination: true,
      showPSR: true,
      showEarthVisibility: true,
      showMLHazard: true,
      showFusedHazard: true,
      mlConfidenceThreshold: 0.65,
      colormap: "magma",
      maxSlopeLimit: 18,
    };

    render(<Moon3DView layers={layers} />);

    expect(screen.getByText(/Active 3D GIS Layers/i)).toBeInTheDocument();
    expect(screen.getByText(/FUSED HAZARD \(FR-13\)/i)).toBeInTheDocument();
    expect(screen.getByText(/ML CRATERS \(65%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/SLOPE >18°/i)).toBeInTheDocument();
    expect(screen.getByText(/SLOPE \(MAGMA\)/i)).toBeInTheDocument();
    expect(screen.getByText(/ROUGHNESS \(TRI\)/i)).toBeInTheDocument();
    expect(screen.getByText(/❄ PSR COLD TRAPS/i)).toBeInTheDocument();
    expect(screen.getByText(/EARTH LINE-OF-SIGHT/i)).toBeInTheDocument();
    expect(screen.getByText(/SOLAR ILLUMINATION/i)).toBeInTheDocument();
  });

  it("renders PolarMap and PlannerPanel with VIPER project data when switched", () => {
    const viperProject = MISSION_PROJECTS["00000000-0000-0000-0000-000000000002"];
    const layers: LayerState = {
      showSlope: false,
      showAspect: false,
      showRoughness: false,
      showHazard: false,
      showHillshade: true,
      showIllumination: false,
      showPSR: false,
      showEarthVisibility: false,
      showMLHazard: false,
      showFusedHazard: false,
      mlConfidenceThreshold: 0.6,
      colormap: "viridis",
      maxSlopeLimit: 12,
    };

    render(<PolarMap layers={layers} onInspect={vi.fn()} project={viperProject} />);
    expect(screen.getByText(/NOBILE \/ MONS MOUTON AOI/i)).toBeInTheDocument();

    render(<PlannerPanel project={viperProject} maxSlopeLimit={12} />);
    expect(screen.getByText(/VIPER \(Volatiles Investigating Polar Rover\)/i)).toBeInTheDocument();
    expect(screen.getByText(/500 Wh/i)).toBeInTheDocument();
  });
});
