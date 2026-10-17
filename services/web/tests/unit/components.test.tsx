import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Banner } from "../../src/components/Banner";
import { Navbar } from "../../src/components/Navbar";
import { LayerControl } from "../../src/features/map/LayerControl";
import { InspectorPanel } from "../../src/features/map/InspectorPanel";
import { TimelineScrubber } from "../../src/features/map/TimelineScrubber";
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
      colormap: "viridis" as const,
      maxSlopeLimit: 15,
    };

    render(<LayerControl layers={initialLayers} onChange={handleChange} />);

    // Click slope toggle
    const slopeBtn = screen.getByText(/Slope \(Horn 3x3\)/i);
    fireEvent.click(slopeBtn);
    expect(handleChange).toHaveBeenCalledWith(
      expect.objectContaining({ showSlope: false })
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
    };

    render(<InspectorPanel inspection={inspection} />);
    expect(screen.getByText("Shackleton Inner Wall")).toBeInTheDocument();
    expect(screen.getByText("-1850.4 m")).toBeInTheDocument();
    expect(screen.getByText("24.3°")).toBeInTheDocument();
    expect(screen.getByText("TERRAIN HAZARD")).toBeInTheDocument();
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
});
