import { LoadingRegion } from "@/components/ui/feedback";

export function MeetingsSkeleton() {
  return (
    <LoadingRegion label="Meetings" className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-2xl bg-white/[0.05]" />
        <div className="space-y-2">
          <div className="h-4 w-52 rounded bg-white/[0.05]" />
          <div className="h-3 w-72 rounded bg-white/[0.03]" />
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <div className="h-40 rounded-[var(--radius-xl)] bg-white/[0.03]" />
          <div className="h-56 rounded-[var(--radius-xl)] bg-white/[0.03]" />
          <div className="h-72 rounded-[var(--radius-xl)] bg-white/[0.03]" />
        </div>
        <div className="space-y-4">
          <div className="h-44 rounded-[var(--radius-xl)] bg-white/[0.03]" />
          <div className="h-44 rounded-[var(--radius-xl)] bg-white/[0.03]" />
        </div>
      </div>
    </LoadingRegion>
  );
}
