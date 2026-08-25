"use client";

import { ArrowRight, Network } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { ENTITY_META, type Entity, type Relationship } from "@/lib/memory/types";

/**
 * A lightweight relationship preview — enough to show that memories are linked
 * (Person→Company, Project→Technology). The full interactive graph is a future
 * milestone; this is intentionally a small, legible list.
 */
export function RelationshipPreview({
  entities,
  relationships,
}: {
  entities: Entity[];
  relationships: Relationship[];
}) {
  const byId = new Map(entities.map((e) => [e.id, e]));
  const edges = relationships.filter((r) => byId.has(r.from) && byId.has(r.to)).slice(0, 6);

  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader
        title="Relationships"
        action={
          <span className="flex items-center gap-1 font-mono text-[10px] text-ink-faint">
            <Network className="h-3 w-3" />
            {relationships.length}
          </span>
        }
      />

      {edges.length === 0 ? (
        <p className="mt-4 text-xs text-ink-faint">No linked entities yet.</p>
      ) : (
        <ul className="mt-4 space-y-2.5">
          {edges.map((e) => {
            const from = byId.get(e.from)!;
            const to = byId.get(e.to)!;
            const FromIcon = ENTITY_META[from.type].icon;
            const ToIcon = ENTITY_META[to.type].icon;
            return (
              <li
                key={e.id}
                className="flex items-center gap-2 rounded-lg bg-white/[0.02] px-2.5 py-2 text-xs"
              >
                <span className="flex min-w-0 items-center gap-1.5 text-ink">
                  <FromIcon className="h-3 w-3 shrink-0 text-violet-bright" />
                  <span className="truncate">{from.label}</span>
                </span>
                <span className="flex shrink-0 items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-ink-faint">
                  <ArrowRight className="h-3 w-3" />
                  {e.kind}
                </span>
                <span className="flex min-w-0 items-center gap-1.5 text-ink">
                  <ToIcon className="h-3 w-3 shrink-0 text-cyan-bright" />
                  <span className="truncate">{to.label}</span>
                </span>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-3 text-[10px] text-ink-faint">
        Interactive memory graph — a future milestone.
      </p>
    </GlassCard>
  );
}
