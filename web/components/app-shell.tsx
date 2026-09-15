"use client";

import { useState } from "react";

import { ControlPlane } from "@/components/control-plane";
import { CustomBuilder } from "@/components/custom-builder";

export function AppShell() {
  const [workspace, setWorkspace] = useState<"modes" | "custom">("modes");

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
      </nav>
      {workspace === "modes" ? <ControlPlane /> : <CustomBuilder />}
    </>
  );
}
