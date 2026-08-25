"use client";

import { CalendarClock } from "lucide-react";
import { ModuleStub } from "@/components/layout/module-stub";

export default function MeetingsPage() {
  return (
    <ModuleStub
      icon={CalendarClock}
      title="Meetings"
      note="Calendar, upcoming meetings, automatic prep, and protected focus windows."
      order="Planned"
    />
  );
}
