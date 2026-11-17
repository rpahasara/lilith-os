import { LoadingRegion } from "@/components/ui/feedback";

export function AutomationsSkeleton() {
  return (
    <LoadingRegion label="Automations" className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-2xl bg-white/[0.05]" />
        <div className="space-y-2">
          <div className="h-4 w-56 rounded bg-white/[0.05]" />
          <div className="h-3 w-72 rounded bg-white/[0.03]" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-44 rounded-[var(--radius-md)] bg-white/[0.03]" />
          ))}
        </div>
        <div className="h-96 rounded-[var(--radius-xl)] bg-white/[0.03]" />
      </div>
    </LoadingRegion>
  );
}
