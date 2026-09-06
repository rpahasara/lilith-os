/**
 * Durable task store for real core tasks.
 *
 * V1 backing is localStorage: durable across reloads and retrievable, which is
 * what the slice requires. It sits behind an interface so a backend-durable
 * implementation (a VM task-store endpoint) can replace it with no core change.
 * Demo fixtures are never written here — only the RealCommandCore persists.
 */
import type { CoreTaskRecord } from "./types";

export interface TaskStore {
  save(record: CoreTaskRecord): void;
  loadAll(): CoreTaskRecord[];
  get(taskId: string): CoreTaskRecord | undefined;
  clear(): void;
}

const KEY = "lilith-os:core-tasks";
const MAX = 50;

export class LocalStorageTaskStore implements TaskStore {
  private mem = new Map<string, CoreTaskRecord>();

  constructor() {
    this.mem = new Map(this.readAll().map((r) => [r.taskId, r]));
  }

  private readAll(): CoreTaskRecord[] {
    try {
      const raw = typeof window !== "undefined" ? window.localStorage.getItem(KEY) : null;
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? (parsed as CoreTaskRecord[]) : [];
    } catch {
      return [];
    }
  }

  private flush() {
    try {
      const list = [...this.mem.values()].sort((a, b) => a.updatedAt - b.updatedAt).slice(-MAX);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(KEY, JSON.stringify(list));
      }
    } catch {
      /* quota / unavailable — stay in-memory */
    }
  }

  save(record: CoreTaskRecord): void {
    this.mem.set(record.taskId, record);
    this.flush();
  }

  loadAll(): CoreTaskRecord[] {
    return [...this.mem.values()].sort((a, b) => a.createdAt - b.createdAt);
  }

  get(taskId: string): CoreTaskRecord | undefined {
    return this.mem.get(taskId);
  }

  clear(): void {
    this.mem.clear();
    try {
      if (typeof window !== "undefined") window.localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }
}

/** In-memory store for tests / SSR. */
export class InMemoryTaskStore implements TaskStore {
  private mem = new Map<string, CoreTaskRecord>();
  save(r: CoreTaskRecord) {
    this.mem.set(r.taskId, r);
  }
  loadAll() {
    return [...this.mem.values()].sort((a, b) => a.createdAt - b.createdAt);
  }
  get(id: string) {
    return this.mem.get(id);
  }
  clear() {
    this.mem.clear();
  }
}
