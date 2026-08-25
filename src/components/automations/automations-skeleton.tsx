export function AutomationsSkeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-xl bg-white/[0.05]" />
        <div className="space-y-2">
          <div className="h-4 w-56 rounded bg-white/[0.05]" />
          <div className="h-3 w-72 rounded bg-white/[0.03]" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-[72px] rounded-[var(--radius-md)] bg-white/[0.03]" />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-44 rounded-[var(--radius-md)] bg-white/[0.03]" />
          ))}
        </div>
        <div className="h-96 rounded-[var(--radius-lg)] bg-white/[0.03]" />
      </div>
    </div>
  );
}
