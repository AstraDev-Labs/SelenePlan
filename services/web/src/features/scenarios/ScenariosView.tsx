import React from "react";
import { Compass, Calendar, BatteryCharging, Gauge, CheckCircle2 } from "lucide-react";

export const ScenariosView: React.FC = () => {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-bold text-white">Mission Scenarios</h2>
          <p className="text-xs text-gray-400">Time-expanded traverse planning parameters and rover constraints.</p>
        </div>
        <button className="btn-primary">Create Scenario</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Active Scenario Card */}
        <div className="glass-panel p-5 flex flex-col gap-4 border-cyan-500/30">
          <div className="flex justify-between items-start">
            <div>
              <span className="badge badge-cyan text-[10px] mb-1">ACTIVE RUN</span>
              <h3 className="text-base font-bold text-white">Artemis-3 Shackleton Ridge Traverse</h3>
              <p className="text-xs text-gray-400">Shackleton Rim to Connecting Ridge Peak</p>
            </div>
            <span className="badge badge-emerald flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Ready
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs font-mono bg-black/40 p-3 rounded-lg border border-white/5">
            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4 text-cyan-400" />
              <div>
                <span className="text-gray-400 block text-[10px]">AOI SPAN</span>
                <span className="text-gray-200">20.0 km x 20.0 km</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-blue-400" />
              <div>
                <span className="text-gray-400 block text-[10px]">TIME WINDOW</span>
                <span className="text-gray-200">14 Earth Days</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Gauge className="w-4 h-4 text-amber-400" />
              <div>
                <span className="text-gray-400 block text-[10px]">MAX SLOPE</span>
                <span className="text-gray-200">15.0&deg;</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <BatteryCharging className="w-4 h-4 text-emerald-400" />
              <div>
                <span className="text-gray-400 block text-[10px]">BATTERY CAPACITY</span>
                <span className="text-gray-200">1,200 Wh</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
