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
      <div className="h-32 rounded-[var(--radius-xl)] bg-white/[0.03]" />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
        <div className="h-96 rounded-[var(--radius-xl)] bg-white/[0.03]" />
        <div className="h-96 rounded-[var(--radius-xl)] bg-white/[0.03]" />
      </div>
    </LoadingRegion>
  );
}
