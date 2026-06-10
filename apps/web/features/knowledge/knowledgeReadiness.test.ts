import { describe, expect, it } from "vitest";

import {
  canStartGeneration,
  canStartKnowledgeOnlyGeneration,
  hasAnalyzedRealSample,
  hasMeaningfulBrief,
  isKnowledgeRecommendationReady,
} from "@/features/knowledge/knowledgeReadiness";

describe("knowledgeReadiness", () => {
  it("treats empty brief as not meaningful", () => {
    expect(hasMeaningfulBrief(null)).toBe(false);
    expect(
      hasMeaningfulBrief({
        sellingPoints: [],
        mustMention: [],
        avoidMention: [],
      }),
    ).toBe(false);
  });

  it("detects meaningful brief fields", () => {
    expect(
      hasMeaningfulBrief({
        topic: "  电商带货  ",
        sellingPoints: [],
        mustMention: [],
        avoidMention: [],
      }),
    ).toBe(true);
  });

  it("detects analyzed real samples but not knowledge imports", () => {
    expect(
      hasAnalyzedRealSample([
        { hasStructure: true, sourceKind: "knowledge", status: "analyzed" },
      ]),
    ).toBe(false);
    expect(
      hasAnalyzedRealSample([
        { hasStructure: true, sourceKind: "local", status: "analyzed" },
      ]),
    ).toBe(true);
  });

  it("allows knowledge recommendation with brief only", () => {
    expect(
      isKnowledgeRecommendationReady({
        hasMeaningfulBrief: false,
        hasPersistedSelection: false,
      }),
    ).toBe(false);
    expect(
      isKnowledgeRecommendationReady({
        hasMeaningfulBrief: true,
        hasPersistedSelection: false,
      }),
    ).toBe(true);
    expect(
      isKnowledgeRecommendationReady({
        hasMeaningfulBrief: false,
        hasPersistedSelection: true,
      }),
    ).toBe(true);
  });

  it("allows generation with brief or real sample", () => {
    expect(
      canStartGeneration({
        hasMeaningfulBrief: false,
        hasAnalyzedRealSample: false,
      }),
    ).toBe(false);
    expect(
      canStartGeneration({
        hasMeaningfulBrief: true,
        hasAnalyzedRealSample: false,
      }),
    ).toBe(true);
    expect(
      canStartGeneration({
        hasMeaningfulBrief: false,
        hasAnalyzedRealSample: true,
      }),
    ).toBe(true);
    expect(
      canStartKnowledgeOnlyGeneration({
        hasMeaningfulBrief: true,
        hasAnalyzedRealSample: false,
      }),
    ).toBe(true);
  });
});
