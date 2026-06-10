type DevProgressMetric = "artifactFetch" | "taskPoll" | "sseReconnect";

const counters: Record<DevProgressMetric, number> = {
  artifactFetch: 0,
  taskPoll: 0,
  sseReconnect: 0,
};

let lastLoggedAt = 0;
const LOG_INTERVAL_MS = 60_000;

export function recordDevProgressMetric(metric: DevProgressMetric): void {
  if (process.env.NODE_ENV !== "development") return;
  counters[metric] += 1;
  const now = Date.now();
  if (now - lastLoggedAt >= LOG_INTERVAL_MS) {
    lastLoggedAt = now;
    console.info("[VideoMaker dev] progress metrics (last 60s window reset)", {
      ...counters,
    });
    counters.artifactFetch = 0;
    counters.taskPoll = 0;
    counters.sseReconnect = 0;
  }
}

export function getDevProgressMetrics(): Readonly<Record<DevProgressMetric, number>> {
  return { ...counters };
}

export function resetDevProgressMetricsForTests(): void {
  counters.artifactFetch = 0;
  counters.taskPoll = 0;
  counters.sseReconnect = 0;
  lastLoggedAt = 0;
}
