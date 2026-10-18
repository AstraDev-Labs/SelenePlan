import React, { useState, useEffect } from "react";
import { Banner } from "@/components/Banner";
import { Navbar } from "@/components/Navbar";
import { PolarMap } from "@/features/map/PolarMap";
import { LayerControl, LayerState } from "@/features/map/LayerControl";
import { InspectorPanel, PointInspection } from "@/features/map/InspectorPanel";
import { PlannerPanel } from "@/features/map/PlannerPanel";
import { ScenariosView } from "@/features/scenarios/ScenariosView";
import { DatasetsView } from "@/features/datasets/DatasetsView";
import { ApprovalsView } from "@/features/approvals/ApprovalsView";
import { IntegrityView } from "@/features/integrity/IntegrityView";
import { AuditView } from "@/features/audit/AuditView";
import { useAuthStore, UserRole } from "@/auth/store";
import { ShieldCheck, UserCog } from "lucide-react";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("map");
  const [inspection, setInspection] = useState<PointInspection | null>(null);

  const [layers, setLayers] = useState<LayerState>({
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
    colormap: "viridis",
    maxSlopeLimit: 15,
  });

  const { isAuthenticated, login, user } = useAuthStore();

  // Initialize with Analyst session by default
  useEffect(() => {
    if (!isAuthenticated) {
      login("mock-token-analyst-1", {
        sub: "user-analyst-1",
        name: "Dr. Eliana Vance",
        email: "e.vance@mission.seleneplan.org",
        roles: ["analyst", "operator"],
        projects: ["00000000-0000-0000-0000-000000000001"],
      });
    }
  }, [isAuthenticated, login]);

  // Role Switcher for paired testing of role-aware UI
  const handleRoleSwitch = (role: UserRole) => {
    login(`mock-token-${role}`, {
      sub: `user-${role}-1`,
      name: `Agent (${role.toUpperCase()})`,
      email: `${role}@mission.seleneplan.org`,
      roles: [role],
      projects: ["00000000-0000-0000-0000-000000000001"],
    });
  };

  return (
    <div className="min-h-screen flex flex-col bg-space-dark text-slate-100">
      <Banner />
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="flex-1 max-w-[1780px] w-full mx-auto px-4 lg:px-8 py-5 flex flex-col gap-5">
        {/* Aerospace Mission Operations Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 glass-panel px-4 py-2 text-xs font-mono">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>LIVE TELEMETRY</span>
            </div>
            <div className="flex items-center gap-2 text-gray-300">
              <UserCog className="w-4 h-4 text-sky-400" />
              <span>Security Clearance: <strong className="text-white capitalize">{user?.roles.join(", ")}</strong></span>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-gray-400 text-[11px] mr-1">Switch Role:</span>
            {(["analyst", "steward", "approver", "auditor", "admin"] as UserRole[]).map((r) => (
              <button
                key={r}
                onClick={() => handleRoleSwitch(r)}
                className={`px-2.5 py-1 rounded text-[11px] capitalize transition-all ${
                  user?.roles.includes(r)
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm shadow-sky-500/20 font-semibold"
                    : "bg-white/5 text-gray-400 hover:text-gray-200 border border-transparent hover:bg-white/10"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Views */}
        {activeTab === "map" && (
          <div className="flex flex-col xl:flex-row gap-5 items-start w-full">
            <div className="flex-1 w-full min-w-0">
              <PolarMap layers={layers} onInspect={setInspection} />
            </div>
            <div className="flex flex-col gap-5 shrink-0 w-full xl:w-[420px]">
              <LayerControl layers={layers} onChange={setLayers} />
              <PlannerPanel />
              <InspectorPanel inspection={inspection} />
            </div>
          </div>
        )}

        {activeTab === "scenarios" && <ScenariosView />}
        {activeTab === "datasets" && <DatasetsView />}
        {activeTab === "approvals" && <ApprovalsView />}
        {activeTab === "integrity" && <IntegrityView />}
        {activeTab === "audit" && <AuditView />}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 py-4 px-6 text-center text-xs text-gray-500 font-mono flex items-center justify-between max-w-[1780px] mx-auto w-full">
        <span>SelenePlan Microservice Framework &copy; 2026 AstraDev Labs</span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-emerald-400">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>In-Memory Auth (No localStorage)</span>
          </span>
          <span>Version 0.1.0-alpha</span>
        </div>
      </footer>
    </div>
  );
};
