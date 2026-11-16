/**
 * SYNTHETIC memory graph for the Cognitive Atlas prototype.
 *
 * Every memory below is invented — a fictional person's life, authored only so
 * the visualization has something believable to show. It is not, and must never
 * be presented as, real LILITH memory. The Atlas UI labels it "Synthetic".
 *
 * Shape of the fiction: threads (tags) recur across domains — a project, a job
 * search, a trip, a few close people — so associations cross regions and a
 * recall has somewhere interesting to travel.
 */
import type { MemoryKind, ProvenanceKind } from "@/lib/memory/types";
import type { BrainLayout } from "./brain-shape";
import { placeNode } from "./brain-shape";
import { hash01 } from "./math";
import { REGIONS, REGION_BY_ID } from "./regions";
import type { AtlasLink, AtlasNode, AtlasNodeInput, RegionId, Vec3 } from "./types";

/** [title, tags, inferred?] */
type Seed = [string, string[], true?];

const DAY = 86_400_000;
/** How far back the fictional memory history reaches. */
export const HISTORY_DAYS = 120;

const SEEDS: Record<RegionId, Seed[]> = {
  career: [
    ["Northwind Labs final round is set for the 21st", ["northwind", "interview"]],
    ["Wants a staff-level role with real design influence", ["goals", "design"]],
    ["Jonas Reiter offered to be a reference", ["jonas", "northwind"]],
    ["Halden's promotion cycle closes in March", ["halden", "goals"]],
    ["Strongest interview stories: the Aurora launch and the Helix rewrite", ["interview", "aurora", "helix"]],
    ["Compensation floor was agreed with Elena", ["elena", "northwind"]],
    ["Northwind's recruiter responds best to async updates", ["northwind", "async"], true],
    ["The portfolio still needs a WebGL case study", ["webgl", "portfolio"]],
    ["Declined the Kestrel offer over its remote policy", ["remote", "goals"]],
    ["Five-year aim: lead a small product studio", ["goals"]],
    ["Talk proposal accepted at Render Conf", ["talk", "webgl"]],
    ["Last review praised cross-team clarity", ["halden", "writing"]],
    ["Negotiation lesson: anchor on scope, not title", ["northwind", "goals"]],
    ["System design is the weakest interview round", ["interview"], true],
    ["Mentoring two junior engineers this quarter", ["halden", "mentoring"]],
    ["Keeps a brag document, updated every Friday", ["writing", "focus"]],
  ],
  projects: [
    ["Aurora — a realtime collaboration canvas, now in beta", ["aurora"]],
    ["Aurora's sync engine moved to CRDTs in the autumn", ["aurora", "crdt"]],
    ["Helix — a weekend audio-synth sketchbook written in Rust", ["helix", "rust", "piano"]],
    ["Aurora's render path is its main performance bottleneck", ["aurora", "webgl"]],
    ["Mira owns Aurora's design system", ["mira", "aurora", "design"]],
    ["Helix needs a preset browser before it can be shared", ["helix"]],
    ["Atlas prototype — GPU particles over React Three Fiber", ["webgl", "atlas"]],
    ["Beta feedback: Aurora's onboarding runs too long", ["aurora", "feedback"]],
    ["The greenhouse sensor rig runs on a Pi in the hallway", ["garden", "hardware"]],
    ["Blog redesign is paused until after the conference", ["writing", "talk"]],
    ["Aurora's offline mode ships behind a flag", ["aurora", "crdt"]],
    ["Helix 0.3 fixed the buffer underrun on macOS", ["helix", "rust"]],
    ["The Lisbon offsite produced Aurora's roadmap", ["lisbon", "aurora"]],
    ["Aurora's auth migration checklist is half done", ["aurora", "security"]],
    ["Photo archive cleanup — 2019 to 2022 still to go", ["photos"]],
    ["The Render Conf demo will run on Aurora's canvas", ["talk", "aurora", "webgl"]],
  ],
  people: [
    ["Mira Castellan — design lead and closest collaborator", ["mira", "design"]],
    ["Jonas Reiter — former manager, now mentor", ["jonas", "mentoring"]],
    ["Elena Marsh — partner; an architect", ["elena", "home"]],
    ["Kai — younger brother, lives in Porto", ["kai", "lisbon"]],
    ["Dr. Anwen Price — physiotherapist", ["health", "running"]],
    ["Tomas Ilves — hiring manager at Northwind", ["northwind", "interview"]],
    ["Priya Raman — Aurora's first beta customer", ["aurora", "feedback"]],
    ["Odile Ferrand — piano teacher, Thursdays", ["piano", "music"]],
    ["Sam Okoro — running partner", ["running"]],
    ["Lena Voss — organiser of Render Conf", ["talk"]],
    ["Idris — the neighbour who waters the plants", ["garden", "home"]],
    ["Hana Sato — staff engineer at Halden, review partner", ["halden", "mentoring"]],
    ["Bruno — Kai's partner, a chef", ["kai", "food"]],
    ["Noor Haddad — recruiter at Northwind", ["northwind", "async"]],
    ["Grandmother Ines — calls every Sunday", ["family", "dates"]],
    ["Felix Brandt — Helix's only other contributor", ["helix", "rust"]],
  ],
  knowledge: [
    ["CRDTs converge without a central coordinator", ["crdt"]],
    ["Point sprites are capped by the GPU's maximum point size", ["webgl"]],
    ["Rust's ownership model rules out data races at compile time", ["rust"]],
    ["Spaced repetition outperforms massed practice", ["learning"]],
    ["Least privilege: grant only what a task needs", ["security"]],
    ["Additive blending fakes bloom at almost no cost", ["webgl", "atlas"]],
    ["Morning light anchors the circadian clock", ["sleep", "health"]],
    ["Portuguese has a personal infinitive", ["language", "lisbon"]],
    ["Nocturnes favour rubato over strict tempo", ["piano", "music"]],
    ["Zone 2 running builds the aerobic base", ["running", "health"]],
    ["PKCE protects OAuth for public clients", ["security"]],
    ["Lines of 60–75 characters read best", ["design", "writing"]],
    ["Tomatoes want six to eight hours of direct sun", ["garden"]],
    ["Anchoring shapes how a negotiation lands", ["goals"]],
    ["Signed distance fields describe a shape implicitly", ["webgl", "atlas"]],
    ["Sunny-16: metering exposure without a meter", ["photos"]],
  ],
  preferences: [
    ["Answer first, detail after", ["style", "writing"]],
    ["Dark, quiet interfaces over busy dashboards", ["design", "style"]],
    ["Async updates beat meetings", ["async", "focus"]],
    ["Deep work happens between 09:00 and 12:00", ["focus"]],
    ["Flat white, no sugar", ["food"]],
    ["Trains over short flights", ["travel"]],
    ["Code review belongs in the afternoon", ["focus", "halden"]],
    ["Metric units and the 24-hour clock", ["style"]],
    ["Long-form reading happens on paper", ["reading"]],
    ["Rust for systems, TypeScript for product", ["rust", "tools"]],
    ["No notifications after 21:00", ["sleep", "focus"]],
    ["Summaries in three bullets, never more", ["style", "writing"]],
    ["Window seat, always", ["travel"]],
    ["Instrumental music while coding", ["music", "focus"]],
    ["Books over gadgets as gifts", ["reading", "dates"]],
    ["Calendar holds need a stated purpose", ["async", "style"]],
  ],
  relationships: [
    ["Mira and Jonas worked together at Halden", ["mira", "jonas", "halden"]],
    ["Elena and Mira met over dinner at the Lisbon offsite", ["elena", "mira", "lisbon"]],
    ["Kai introduced Bruno to the family in June", ["kai", "family"]],
    ["Jonas made the introduction to Tomas Ilves's team", ["jonas", "northwind"]],
    ["Sam and Dr. Price both advise easing the mileage", ["running", "health"]],
    ["Priya's feedback reaches the team through Mira first", ["mira", "feedback", "aurora"]],
    ["Odile suggested the Nocturne after the spring recital", ["piano", "music"]],
    ["Anniversary with Elena: the second weekend of May", ["elena", "dates"]],
    ["Hana and Felix know each other from a Rust meetup", ["rust", "halden", "helix"]],
    ["Trust with Noor was built on fast, honest replies", ["northwind", "async"], true],
    ["Grandmother Ines taught the tomato trick", ["family", "garden"]],
    ["Lena invited Mira to co-present", ["talk", "mira"]],
    ["Idris and Elena share a studio lease", ["home", "elena"]],
    ["Kai and Elena are planning the winter visit to Porto", ["kai", "elena", "travel"]],
    ["Tension with Tomas over the timeline was settled by a call", ["northwind", "interview"], true],
    ["Mira is the first to hear about big decisions", ["mira", "goals"], true],
  ],
  personal: [
    ["Lives in a top-floor flat with north light", ["home"]],
    ["Birthday falls in late November", ["dates"]],
    ["Runs three mornings a week along the canal", ["running", "health"]],
    ["Sleeps best after a 23:00 wind-down", ["sleep", "health"]],
    ["Learning Chopin's Nocturne in E-flat", ["piano", "music"]],
    ["A mild knee strain since the spring half-marathon", ["running", "health"]],
    ["Grew up near the coast and misses the sea", ["home", "travel"]],
    ["Vegetarian on weekdays", ["food", "health"]],
    ["Keeps a paper journal on Sundays", ["writing", "focus"]],
    ["The Lisbon trip was the best week of the year", ["lisbon", "travel"]],
    ["Allergic to penicillin", ["health"]],
    ["Grows basil and tomatoes on the balcony", ["garden", "home"]],
    ["Mood dips in winter — light and exercise help", ["health", "sleep"], true],
    ["Speaks conversational Portuguese", ["lisbon", "language"]],
    ["Shoots film on a 35mm rangefinder", ["photos"]],
    ["Saturday mornings are protected time", ["focus", "home"]],
  ],
};

/** Memories the live simulation "learns" during a session. */
export const LEARN_POOL: { region: RegionId; seed: Seed }[] = [
  { region: "career", seed: ["Northwind sent the system-design brief", ["northwind", "interview"]] },
  { region: "projects", seed: ["Aurora's beta crossed four hundred weekly teams", ["aurora", "feedback"]] },
  { region: "people", seed: ["Tomas Ilves prefers whiteboard-first interviews", ["northwind", "interview"], true] },
  { region: "knowledge", seed: ["Instanced points scale past 100k on integrated GPUs", ["webgl", "atlas"]] },
  { region: "personal", seed: ["Booked the train to Porto for the 14th", ["travel", "kai"]] },
  { region: "relationships", seed: ["Mira and Lena agreed on the talk outline", ["talk", "mira"]] },
  { region: "preferences", seed: ["Recall summaries should carry their sources", ["style", "writing"]] },
  { region: "projects", seed: ["Helix gained a MIDI input path", ["helix", "piano"]] },
  { region: "career", seed: ["Jonas suggested asking for a design-review seat", ["jonas", "goals", "design"]] },
  { region: "knowledge", seed: ["Tapering mileage two weeks out protects the knees", ["running", "health"]] },
  { region: "people", seed: ["Priya Raman is moving Aurora to her whole studio", ["aurora", "feedback"]] },
  { region: "personal", seed: ["First full run of the Nocturne without stopping", ["piano", "music"]] },
  { region: "relationships", seed: ["Elena and Kai settled the Porto dates", ["elena", "kai", "travel"]] },
  { region: "preferences", seed: ["Interview prep works best in the morning block", ["focus", "interview"], true] },
  { region: "projects", seed: ["Aurora's canvas now batches draws per layer", ["aurora", "webgl"]] },
  { region: "knowledge", seed: ["Last-writer-wins registers lose concurrent edits", ["crdt"]] },
  { region: "career", seed: ["Render Conf moved the talk to the main stage", ["talk", "webgl"]] },
  { region: "people", seed: ["Odile Ferrand is holding a winter recital", ["piano", "music"]] },
  { region: "personal", seed: ["Light box on the desk from the first week of November", ["sleep", "health"]] },
  { region: "relationships", seed: ["Hana offered to rehearse the system-design round", ["halden", "interview", "mentoring"]] },
  { region: "preferences", seed: ["Travel days stay meeting-free", ["travel", "async"]] },
];

/** Tags that name an entity — surfaced as "related entities" in the inspector. */
const ENTITIES: Record<string, string> = {
  aurora: "Aurora",
  helix: "Helix",
  atlas: "Atlas prototype",
  northwind: "Northwind Labs",
  halden: "Halden",
  mira: "Mira Castellan",
  jonas: "Jonas Reiter",
  elena: "Elena Marsh",
  kai: "Kai",
  lisbon: "Lisbon",
  talk: "Render Conf",
  piano: "Piano",
  family: "Family",
};

const SOURCES: Record<RegionId, ProvenanceKind[]> = {
  career: ["career_event", "gmail", "calendar", "conversation"],
  projects: ["project_data", "conversation", "project_data"],
  people: ["gmail", "conversation", "calendar"],
  knowledge: ["curated_memory", "manual", "project_data"],
  preferences: ["manual", "conversation", "curated_memory"],
  relationships: ["conversation", "gmail", "calendar"],
  personal: ["conversation", "manual", "calendar"],
};

const SOURCE_LINE: Record<ProvenanceKind, string> = {
  conversation: "Said in conversation",
  gmail: "Read from an email thread",
  calendar: "Read from a calendar entry",
  manual: "Recorded on request",
  inferred: "Inferred from repeated patterns",
  automation: "Captured by an automation",
  project_data: "Read from project data",
  career_event: "Logged from the career pipeline",
  curated_memory: "Kept in curated memory",
  unknown: "Source not stated",
};

/** Expand an authored seed into a full memory. Deterministic per id. */
export function seedToInput(id: string, region: RegionId, seed: Seed, createdAt: number): AtlasNodeInput {
  const [title, tags, inferred] = seed;
  const kind: MemoryKind = inferred ? "inference" : "fact";
  const sources = SOURCES[region];
  const source: ProvenanceKind = inferred
    ? "inferred"
    : sources[Math.floor(hash01(id, 1) * sources.length)];
  const confidence = inferred
    ? 48 + Math.round(hash01(id, 2) * 24)
    : 80 + Math.round(hash01(id, 2) * 19);
  const importance = 30 + Math.round(Math.pow(hash01(id, 3), 1.6) * 68);
  const context = REGION_BY_ID[region].blurb;
  return {
    id,
    region,
    title,
    detail: inferred
      ? `${title}. Lilith inferred this from patterns rather than hearing it directly — it may be wrong. ${context}`
      : `${title}. Held as a fact, stated or observed directly. ${context}`,
    kind,
    tags,
    entities: tags.filter((t) => ENTITIES[t]).map((t) => ENTITIES[t]),
    provenance: { kind: source, label: SOURCE_LINE[source], at: createdAt },
    confidence,
    importance,
    createdAt,
  };
}

export interface SyntheticGraph {
  nodes: AtlasNode[];
  links: AtlasLink[];
  /** start of the growth timeline (epoch ms). */
  origin: number;
  now: number;
}

/** History fraction (0 = oldest) for a timestamp. Live arrivals pin to the end. */
export function bornAt(createdAt: number, origin: number, now: number): number {
  return Math.min(0.96, Math.max(0, ((createdAt - origin) / (now - origin)) * 0.96));
}

export function buildSyntheticGraph(layout: BrainLayout, now = Date.now()): SyntheticGraph {
  const origin = now - HISTORY_DAYS * DAY;
  const nodes: AtlasNode[] = [];
  const taken: Vec3[] = [];

  for (const region of REGIONS) {
    SEEDS[region.id].forEach((seed, i) => {
      const id = `${region.id}-${String(i + 1).padStart(2, "0")}`;
      // growth accelerates: recent weeks hold more memories than early ones
      const age = (1 - Math.pow(hash01(id, 5), 0.62)) * (HISTORY_DAYS - 1) + 0.4;
      const createdAt = Math.round(now - age * DAY);
      const input = seedToInput(id, region.id, seed, createdAt);
      // the first few in every domain are its anchors
      if (i < 3) input.importance = Math.max(input.importance, 82 + Math.round(hash01(id, 4) * 14));
      const position = placeNode(layout, region.id, id, taken);
      taken.push(position);
      const reinforcements = Math.round(hash01(id, 6) * 7);
      nodes.push({
        ...input,
        position,
        born: bornAt(createdAt, origin, now),
        live: false,
        reinforcements,
        recalls: Math.round(hash01(id, 7) * 12),
        reinforcedAt: reinforcements
          ? Math.round(createdAt + hash01(id, 8) * (now - createdAt))
          : undefined,
      });
    });
  }

  /* links ----------------------------------------------------------------- */
  const links: AtlasLink[] = [];
  const seen = new Set<string>();
  const connect = (a: AtlasNode, b: AtlasNode, kind: string, strength: number) => {
    if (a.id === b.id) return;
    const key = a.id < b.id ? `${a.id}|${b.id}` : `${b.id}|${a.id}`;
    if (seen.has(key)) return;
    seen.add(key);
    const createdAt = Math.max(a.createdAt, b.createdAt) + 3_600_000;
    links.push({
      id: `l-${links.length + 1}`,
      source: a.id,
      target: b.id,
      kind,
      strength,
      createdAt,
      born: bornAt(createdAt, origin, now),
      live: false,
    });
  };

  // shared threads — the semantic backbone; these are what cross domains
  const byTag = new Map<string, AtlasNode[]>();
  for (const n of nodes) for (const t of n.tags) byTag.set(t, [...(byTag.get(t) ?? []), n]);
  for (const [tag, group] of byTag) {
    if (group.length < 2) continue;
    const ordered = [...group].sort((a, b) => hash01(a.id + tag) - hash01(b.id + tag));
    for (let i = 0; i < ordered.length - 1; i++) {
      connect(ordered[i], ordered[i + 1], `shares · ${tag}`, 0.6 + hash01(ordered[i].id + tag, 2) * 0.35);
      if (ordered.length >= 6 && i % 3 === 0 && i + 2 < ordered.length) {
        connect(ordered[i], ordered[i + 2], `shares · ${tag}`, 0.5 + hash01(ordered[i].id + tag, 3) * 0.3);
      }
    }
  }

  // local structure — each memory ties to its nearest neighbour in the domain
  for (const n of nodes) {
    let nearest: AtlasNode | null = null;
    let best = Infinity;
    for (const m of nodes) {
      if (m.id === n.id || m.region !== n.region) continue;
      // stay within a hemisphere so local ties never cut across the fissure
      if (Math.sign(m.position[2]) !== Math.sign(n.position[2])) continue;
      const d = Math.hypot(
        m.position[0] - n.position[0],
        m.position[1] - n.position[1],
        m.position[2] - n.position[2],
      );
      if (d < best) {
        best = d;
        nearest = m;
      }
    }
    if (nearest) connect(n, nearest, `same domain · ${REGION_BY_ID[n.region].label.toLowerCase()}`, 0.32 + hash01(n.id, 9) * 0.22);
  }

  return { nodes, links, origin, now };
}
