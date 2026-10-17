import React from "react";
import { AlertTriangle, Info } from "lucide-react";

export const Banner: React.FC = () => {
  return (
    <aside
      aria-label="Scientific Assumptions and Mission Advisory"
      className="bg-amber-950/40 border-b border-amber-500/20 px-4 py-1.5 flex items-center justify-between text-xs text-amber-200/90 font-mono"
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" aria-hidden="true" />
        <span>
          <strong className="font-semibold text-amber-300">ADVISORY:</strong> Not flight-qualified; engineering & scientific assumptions apply.
        </span>
      </div>
      <div className="hidden sm:flex items-center gap-4 text-amber-400/80">
        <span className="flex items-center gap-1">
          <Info className="w-3 h-3" aria-hidden="true" />
          Moon Radius: 1,737.4 km (IAU 2015 Sphere)
        </span>
        <span>CRS: IAU_2015:30100 (Stereographic)</span>
      </div>
    </aside>
  );
};
