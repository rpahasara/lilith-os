import { LoadingRegion } from "@/components/ui/feedback";

export function CareerSkeleton() {
  return (
    <LoadingRegion label="Career" className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-2xl bg-white/[0.05]" />
        <div className="space-y-2">
          <div className="h-4 w-48 rounded bg-white/[0.05]" />
          <div className="h-3 w-64 rounded bg-white/[0.03]" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-[72px] rounded-[var(--radius-md)] bg-white/[0.03]" />
        ))}
      </div>
      <div className="h-32 rounded-[var(--radius-xl)] bg-white/[0.03]" />
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="h-96 rounded-[var(--radius-xl)] bg-white/[0.03]" />
        <div className="h-96 rounded-[var(--radius-xl)] bg-white/[0.03]" />
      </div>
    </LoadingRegion>
  );
}
