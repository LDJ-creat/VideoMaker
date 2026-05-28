import type { DataSource } from "@/lib/api-types";

type Listener = (source: DataSource | null) => void;

let current: DataSource | null = null;
const listeners = new Set<Listener>();

export function setLastDataSource(source: DataSource | null): void {
  current = source;
  listeners.forEach((listener) => listener(current));
}

export function getLastDataSource(): DataSource | null {
  return current;
}

export function subscribeDataSource(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
