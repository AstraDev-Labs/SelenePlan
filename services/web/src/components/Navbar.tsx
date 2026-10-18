import React from "react";
import {
  Compass,
  Layers,
  ShieldCheck,
  FileCheck2,
  Database,
  Activity,
  LogOut,
  UserCircle
} from "lucide-react";
import { useAuthStore } from "@/auth/store";

interface NavbarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onTabChange }) => {
  const { user, isAuthenticated, logout, hasRole, activeProjectId, setActiveProject } = useAuthStore();

  const navItems = [
    { id: "map", label: "Polar Map", icon: Compass, roles: ["analyst", "operator", "admin", "approver", "steward", "auditor"] },
    { id: "scenarios", label: "Scenarios", icon: Layers, roles: ["analyst", "operator", "admin"] },
    { id: "datasets", label: "Datasets", icon: Database, roles: ["steward", "admin"] },
    { id: "approvals", label: "Approvals", icon: FileCheck2, roles: ["approver", "admin"] },
    { id: "integrity", label: "Integrity", icon: ShieldCheck, roles: ["analyst", "operator", "approver", "steward", "admin", "auditor"] },
    { id: "audit", label: "Audit Log", icon: Activity, roles: ["auditor", "admin"] },
  ];

  const availableNav = navItems.filter((item) =>
    item.roles.some((r) => hasRole(r as any))
  );

  return (
    <header className="glass-panel border-x-0 border-t-0 rounded-none px-6 py-3 flex items-center justify-between sticky top-0 z-40">
      {/* Brand & Project Selector */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500/20 to-blue-600/30 border border-sky-400/40 flex items-center justify-center shadow-lg shadow-sky-500/20 backdrop-blur-sm relative overflow-hidden group shrink-0" style={{ width: 36, height: 36, minWidth: 36 }}>
            <div className="absolute inset-0 bg-sky-400/10 opacity-0 group-hover:opacity-100 transition-opacity" />
            <img src="/moon.svg" alt="SelenePlan Lunar Emblem" className="brand-emblem object-contain drop-shadow" style={{ width: 26, height: 26, maxWidth: 26, maxHeight: 26 }} width={26} height={26} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-white leading-none">
                Selene<span className="text-sky-400">Plan</span>
              </h1>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-sky-500/10 border border-sky-500/30 text-sky-300">
                LUNAR MISSION OS
              </span>
            </div>
            <p className="text-[10px] text-gray-400 font-mono tracking-wider mt-0.5">SHACKLETON POLAR AOI</p>
          </div>
        </div>

        {/* Project Selector */}
        <div className="hidden md:flex items-center gap-2 border-l border-white/10 pl-6">
          <label htmlFor="project-select" className="text-xs text-gray-400 font-mono">Project:</label>
          <select
            id="project-select"
            aria-label="Active Mission Project"
            value={activeProjectId}
            onChange={(e) => setActiveProject(e.target.value)}
            className="bg-gray-900 border border-white/10 rounded px-2.5 py-1 text-xs text-cyan-300 font-mono focus:outline-none focus:border-cyan-400"
          >
            <option value="00000000-0000-0000-0000-000000000001">Artemis-3 (Shackleton)</option>
            <option value="00000000-0000-0000-0000-000000000002">VIPER-Extended (Nobile)</option>
          </select>
        </div>
      </div>

      {/* Navigation tabs */}
      <nav aria-label="Main Navigation" className="flex items-center gap-1">
        {availableNav.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-colors ${
                isActive
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  : "text-gray-400 hover:text-gray-200 hover:bg-white/5"
              }`}
            >
              <Icon className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* User profile & Auth */}
      <div className="flex items-center gap-3">
        {isAuthenticated && user ? (
          <div className="flex items-center gap-3">
            <div className="hidden lg:flex flex-col items-end text-right">
              <span className="text-xs font-semibold text-gray-200">{user.name}</span>
              <span className="text-[10px] text-cyan-400 font-mono capitalize">
                {user.roles.join(", ")}
              </span>
            </div>
            <button
              onClick={logout}
              aria-label="Log Out"
              title="Log Out (In-Memory Session)"
              className="p-1.5 text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 rounded border border-transparent hover:border-rose-500/20 transition-colors"
            >
              <LogOut className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <UserCircle className="w-4 h-4 text-gray-400" aria-hidden="true" />
            <span className="text-xs text-gray-400">Guest</span>
          </div>
        )}
      </div>
    </header>
  );
};
