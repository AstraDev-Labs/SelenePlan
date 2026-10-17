import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import axe from "axe-core";
import { Banner } from "../../src/components/Banner";
import { Navbar } from "../../src/components/Navbar";
import { TimelineScrubber } from "../../src/features/map/TimelineScrubber";

describe("Accessibility (WCAG 2.1 AA Standards)", () => {
  it("Banner component has no accessibility violations", async () => {
    const { container } = render(<Banner />);
    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });

  it("Navbar component has no accessibility violations", async () => {
    const { container } = render(<Navbar activeTab="map" onTabChange={() => {}} />);
    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });

  it("TimelineScrubber component has no accessibility violations", async () => {
    const { container } = render(
      <TimelineScrubber
        totalSteps={24}
        currentStep={5}
        onStepChange={() => {}}
        timestamps={Array.from({ length: 24 }, (_, i) => `2026-03-01T0${i}:00:00Z`)}
      />
    );
    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });
});
