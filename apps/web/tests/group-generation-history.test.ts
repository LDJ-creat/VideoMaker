import { describe, expect, it } from "vitest";

import {
  collectKnownGenerationIds,
  countDirectReviseForks,
  indexRevisionsBySource,
  listOrphanRevisions,
} from "@/lib/groupGenerationHistory";
import type { ReviseGenerationSummary } from "@/lib/apiClient";

describe("groupGenerationHistory", () => {
  const revisions: ReviseGenerationSummary[] = [
    {
      generationId: "fork-1",
      sourceGenerationId: "gen-b",
      instruction: "center layout",
      updatedAt: "2026-06-27T03:00:00Z",
      variant: "high_conversion",
    },
    {
      generationId: "fork-2",
      sourceGenerationId: "gen-b",
      instruction: "older edit",
      updatedAt: "2026-06-26T03:00:00Z",
      variant: "high_conversion",
    },
    {
      generationId: "fork-orphan",
      sourceGenerationId: "missing-source",
      instruction: "orphan",
      updatedAt: "2026-06-25T03:00:00Z",
    },
  ];

  it("indexes revisions by source generation id", () => {
    const indexed = indexRevisionsBySource(revisions);
    expect(indexed.get("gen-b")?.map((entry) => entry.generationId)).toEqual([
      "fork-1",
      "fork-2",
    ]);
  });

  it("lists orphan revisions when source is not in known runs", () => {
    const known = collectKnownGenerationIds({
      "run-1": [{ generationId: "gen-a" }, { generationId: "gen-b" }],
    });
    expect(listOrphanRevisions(revisions, known).map((entry) => entry.generationId)).toEqual([
      "fork-orphan",
    ]);
  });

  it("counts direct revise forks for delete confirmation", () => {
    expect(countDirectReviseForks(revisions, "gen-b")).toBe(2);
  });
});
