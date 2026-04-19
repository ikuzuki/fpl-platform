import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";

// jsdom 29 + vitest 4 don't always expose a working `localStorage` on
// `window` (the runtime warns about a missing `--localstorage-file` flag).
// Install a minimal in-memory shim so tests that touch storage work
// uniformly across runners.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length(): number {
    return this.store.size;
  }
  clear(): void {
    this.store.clear();
  }
  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }
  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }
  removeItem(key: string): void {
    this.store.delete(key);
  }
  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}

const memoryStorage = new MemoryStorage();
Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: memoryStorage,
});

// Fallback for environments where window.crypto.randomUUID is missing.
if (!window.crypto?.randomUUID) {
  Object.defineProperty(window, "crypto", {
    configurable: true,
    value: {
      ...window.crypto,
      randomUUID: () =>
        "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
          const r = (Math.random() * 16) | 0;
          const v = c === "x" ? r : (r & 0x3) | 0x8;
          return v.toString(16);
        }),
    },
  });
}

afterEach(() => {
  memoryStorage.clear();
});
