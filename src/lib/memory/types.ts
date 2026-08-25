/**
 * Memory domain types — LILITH's persistent cognitive memory.
 *
 * This is NOT a notes app: a MemoryRecord is something Lilith *knows* — a fact
 * or an inference — with a category, an entity it concerns, provenance (why she
 * knows it), a confidence, and links to related memories and entities.
 *
 * The shapes below are the UI contract. A future backend will expose:
 *   GET /memory/overview
 *   GET /memory/records?category=&entity=&limit=
 *   GET /memory/entities?type=
 *   GET /memory/search?q=&scope=memory|conversation
 * Until those exist, the client (client.ts) falls back to the isolated demo
 * adapter (demo.ts). Live and demo data are NEVER mixed.
 */

import type { LucideIcon } from "lucide-react";
import {
  Users,
  FolderKanban,
  Briefcase,
  Building2,
  User,
  Sliders,
  BookOpen,
  MessageSquare,
  Mail,
  CalendarDays,
  PenLine,
  Sparkles,
  Workflow,
  Database,
  GitBranch,
  BookMarked,
} from "lucide-react";

/* ----------------------------------------------------------------- categories */

export const CATEGORIES = [
  "people",
  "projects",
  "career",
  "work",
  "personal",
  "preferences",
  "knowledge",
] as const;

export type MemoryCategory = (typeof CATEGORIES)[number];

export type Accent = "violet" | "cyan" | "green" | "amber" | "rose" | "faint";

export const CATEGORY_META: Record<
  MemoryCategory,
  { label: string; accent: Accent; icon: LucideIcon; blurb: string }
> = {
  people: { label: "People", accent: "violet", icon: Users, blurb: "Relationships & contacts" },
  projects: { label: "Projects", accent: "cyan", icon: FolderKanban, blurb: "What you're building" },
  career: { label: "Career", accent: "amber", icon: Briefcase, blurb: "Roles & opportunities" },
  work: { label: "Work", accent: "cyan", icon: Building2, blurb: "How you work" },
  personal: { label: "Personal", accent: "violet", icon: User, blurb: "Context about you" },
  preferences: { label: "Preferences", accent: "green", icon: Sliders, blurb: "How you like things" },
  knowledge: { label: "Knowledge", accent: "cyan", icon: BookOpen, blurb: "Facts & references" },
};

/* ---------------------------------------------------------------- entity types */

export type EntityType =
  | "person"
  | "company"
  | "project"
  | "application"
  | "technology"
  | "place"
  | "concept";

export const ENTITY_META: Record<EntityType, { label: string; icon: LucideIcon }> = {
  person: { label: "Person", icon: User },
  company: { label: "Company", icon: Building2 },
  project: { label: "Project", icon: FolderKanban },
  application: { label: "Application", icon: Briefcase },
  technology: { label: "Technology", icon: GitBranch },
  place: { label: "Place", icon: CalendarDays },
  concept: { label: "Concept", icon: BookOpen },
};

/* ------------------------------------------------------------------ provenance */

/** Where a memory came from — the answer to "why does Lilith know this?". */
export type ProvenanceKind =
  | "conversation"
  | "gmail"
  | "calendar"
  | "manual"
  | "inferred"
  | "automation"
  | "project_data"
  | "career_event"
  | "curated_memory";

export const PROVENANCE_META: Record<
  ProvenanceKind,
  { label: string; icon: LucideIcon; accent: Accent }
> = {
  conversation: { label: "Conversation", icon: MessageSquare, accent: "violet" },
  gmail: { label: "Gmail", icon: Mail, accent: "cyan" },
  calendar: { label: "Calendar", icon: CalendarDays, accent: "cyan" },
  manual: { label: "Manual", icon: PenLine, accent: "green" },
  inferred: { label: "Inferred", icon: Sparkles, accent: "amber" },
  automation: { label: "Automation", icon: Workflow, accent: "cyan" },
  project_data: { label: "Project data", icon: Database, accent: "cyan" },
  career_event: { label: "Career event", icon: Briefcase, accent: "amber" },
  curated_memory: { label: "Curated memory", icon: BookMarked, accent: "green" },
};

export interface Provenance {
  kind: ProvenanceKind;
  /** connected account/system, e.g. "gmail · primary" — optional. */
  sourceAccount?: string;
  /** human "why Lilith knows this". */
  label: string;
  /** ISO timestamp of the originating signal, when known. */
  at?: string;
}

/**
 * FACT vs INFERENCE — a first-class distinction. A fact was stated/observed
 * directly; an inference was derived by Lilith and may be wrong.
 */
export type MemoryKind = "fact" | "inference";

/* --------------------------------------------------------------- core records */

/** A lightweight reference to an entity a memory concerns. */
export interface EntityRef {
  id: string;
  type: EntityType;
  label: string;
}

export interface MemoryRecord {
  id: string;
  /** short one-line summary shown on the card. */
  summary: string;
  /** full memory content shown in the detail drawer. */
  content: string;
  category: MemoryCategory;
  kind: MemoryKind;
  /** entities this memory is about. */
  entities: EntityRef[];
  /** 0–100 confidence; undefined when the source doesn't express one. */
  confidence?: number;
  /** 0–100 importance; drives constellation node size & ordering. */
  importance?: number;
  pinned?: boolean;
  tags: string[];
  provenance: Provenance;
  createdAt?: string; // ISO
  updatedAt?: string; // ISO
  lastAccessed?: string; // ISO
  /** ids of related memories (for the detail drawer). */
  related: string[];
}

/** An entity in Lilith's world — feeds the relationship preview. */
export interface Entity {
  id: string;
  type: EntityType;
  label: string;
  subtitle?: string;
  /** how many memories reference this entity. */
  memoryCount: number;
}

/** A directed relationship between two entities (Person→Company, etc.). */
export interface Relationship {
  id: string;
  from: string; // entity id
  to: string; // entity id
  /** human label for the edge, e.g. "works at", "built with". */
  kind: string;
}

/* ----------------------------------------------------------------- aggregates */

export interface RecentMemoryEvent {
  id: string;
  at: string; // ISO
  text: string;
  category: MemoryCategory;
  kind: "learned" | "updated" | "reinforced";
}

export interface MemoryOverview {
  total: number;
  /** learned in the last 7 days. */
  recentlyLearned: number;
  pinned: number;
  /** distinct categories in use. */
  categories: number;
  entities: number;
  /** average confidence across records that carry one (0–100). */
  avgConfidence: number;
  byCategory: Record<MemoryCategory, number>;
  bySource: Partial<Record<ProvenanceKind, number>>;
  recentActivity: RecentMemoryEvent[];
}

/** Everything the Memory workspace needs, plus provenance/connection state. */
export interface MemoryData {
  overview: MemoryOverview;
  records: MemoryRecord[];
  entities: Entity[];
  relationships: Relationship[];
  /** true when served from the isolated demo adapter (no live backend). */
  isDemo: boolean;
  diagnostics?: import("@/lib/api").Diagnostics;
}

/** Search scope — curated memory vs raw conversation recall (future). */
export type SearchScope = "memory" | "conversation";

/* -------------------------------------------------------------------- helpers */

const CONFIDENCE_TIERS = [
  { min: 85, label: "High", accent: "green" as Accent },
  { min: 60, label: "Medium", accent: "cyan" as Accent },
  { min: 0, label: "Low", accent: "amber" as Accent },
];

export function confidenceTier(value?: number): {
  label: string;
  accent: Accent;
} {
  if (value == null) return { label: "Unknown", accent: "faint" };
  return (
    CONFIDENCE_TIERS.find((t) => value >= t.min) ?? {
      label: "Low",
      accent: "amber",
    }
  );
}
