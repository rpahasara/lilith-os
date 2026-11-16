"use client";

import dynamic from "next/dynamic";

/**
 * /memory/atlas — the Cognitive Atlas prototype (Brain + Timeline views).
 *
 * Client-only on purpose: the atlas builds its synthetic graph from the current
 * time and renders WebGL, so there is nothing meaningful to prerender. The
 * existing, backend-wired Memory workspace stays at /memory, untouched.
 */
const CognitiveAtlas = dynamic(() => import("@/components/memory/atlas/cognitive-atlas"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full min-h-[480px] place-items-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-44 w-60 rounded-[50%] bg-[radial-gradient(circle,rgba(201,84,115,0.4),rgba(91,199,216,0.1)_55%,transparent_72%)] blur-2xl animate-breathe" />
        <p className="eyebrow">Assembling the atlas…</p>
      </div>
    </div>
  ),
});

export default function MemoryAtlasPage() {
  return (
    <div className="h-full pb-1">
      <CognitiveAtlas />
    </div>
  );
}
