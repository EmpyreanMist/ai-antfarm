"use client";

import { useState } from "react";

import { ControlPlane } from "@/components/control-plane";
import { CustomBuilder } from "@/components/custom-builder";
import { HistoryExplorer } from "@/components/history-explorer";

export function AppShell() {
  const [workspace, setWorkspace] = useState<"modes" | "custom" | "history">("modes");

  return (
    <>
      <nav className="workspace-switch" aria-label="Simulation workspace">
        <button
          type="button"
          aria-pressed={workspace === "modes"}
          onClick={() => setWorkspace("modes")}
        >
          Game modes
        </button>
        <button
          type="button"
          aria-pressed={workspace === "custom"}
          onClick={() => setWorkspace("custom")}
        >
          Custom builder
        </button>
        <button
          type="button"
          aria-pressed={workspace === "history"}
          onClick={() => setWorkspace("history")}
        >
          History & replay
        </button>
      </nav>
      {workspace === "modes" && <ControlPlane />}
      {workspace === "custom" && <CustomBuilder />}
      {workspace === "history" && <HistoryExplorer />}
    </>
  );
}
