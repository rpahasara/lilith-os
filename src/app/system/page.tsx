"use client";

import { Activity } from "lucide-react";
import { ModuleStub } from "@/components/layout/module-stub";

export default function SystemPage() {
  return (
    <ModuleStub
      icon={Activity}
      title="System"
      note="Health, telemetry, privacy controls, and connected integrations."
      order="Planned"
    />
  );
}
