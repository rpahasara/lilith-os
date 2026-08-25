"use client";

import { Brain } from "lucide-react";
import { ModuleStub } from "@/components/layout/module-stub";

export default function MemoryPage() {
  return (
    <ModuleStub
      icon={Brain}
      title="Memory"
      note="Lilith's living knowledge graph — facts, projects, and people."
      order="Next up · after Automations"
    />
  );
}
