import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock Canvas 2D and WebGL context for map rendering tests
HTMLCanvasElement.prototype.getContext = vi.fn().mockImplementation(function (this: any, contextId: string) {
  if (contextId === "webgl" || contextId === "webgl2" || contextId === "experimental-webgl") {
    const glTarget: Record<string, any> = {
      VERSION: 7938,
      SHADING_LANGUAGE_VERSION: 35724,
      VENDOR: 7936,
      RENDERER: 7937,
      getExtension: vi.fn(),
      getParameter: vi.fn().mockImplementation((p: any) => {
        if (p === 7938 || p === 35724 || p === 7936 || p === 7937 || !p) return "WebGL 1.0";
        return 16;
      }),
      getProgramParameter: vi.fn().mockImplementation((_prog: any, param: any) => {
        // LINK_STATUS = 35714
        if (param === 35714) return true;
        // ACTIVE_UNIFORMS = 35718, ACTIVE_ATTRIBUTES = 35721
        if (param === 35718 || param === 35721) return 0;
        return 0;
      }),
      getShaderPrecisionFormat: vi.fn().mockReturnValue({ precision: 23, rangeMin: 127, rangeMax: 127 }),
      getShaderParameter: vi.fn().mockReturnValue(true),
      getActiveUniform: vi.fn().mockReturnValue({ name: "dummy", size: 1, type: 35665 }),
      getActiveAttrib: vi.fn().mockReturnValue({ name: "position", size: 1, type: 35665 }),
      getImageData: vi.fn().mockReturnValue({ data: new Uint8ClampedArray(4) }),
      canvas: this,
    };
    return new Proxy(glTarget, {
      get(target, prop) {
        if (prop in target) {
          return target[prop as string];
        }
        if (typeof prop === "string" && !target[prop]) {
          target[prop] = vi.fn();
          return target[prop];
        }
        return undefined;
      },
    });
  }
  const ctx2dTarget: Record<string, any> = {
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    getImageData: vi.fn().mockReturnValue({ data: new Uint8ClampedArray(4) }),
    putImageData: vi.fn(),
    createImageData: vi.fn().mockReturnValue({ data: new Uint8ClampedArray(4) }),
    createRadialGradient: vi.fn().mockReturnValue({ addColorStop: vi.fn() }),
    createLinearGradient: vi.fn().mockReturnValue({ addColorStop: vi.fn() }),
    setTransform: vi.fn(),
    drawImage: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    closePath: vi.fn(),
    stroke: vi.fn(),
    fill: vi.fn(),
    arc: vi.fn(),
    scale: vi.fn(),
    translate: vi.fn(),
    rotate: vi.fn(),
    canvas: this,
  };
  return new Proxy(ctx2dTarget, {
    get(target, prop) {
      if (prop in target) {
        return target[prop as string];
      }
      if (typeof prop === "string" && !target[prop]) {
        target[prop] = vi.fn();
        return target[prop];
      }
      return undefined;
    },
  });
}) as any;
