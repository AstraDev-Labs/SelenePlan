import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import axe from "axe-core";
import { Banner } from "../../src/components/Banner";
import { Navbar } from "../../src/components/Navbar";

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
});
