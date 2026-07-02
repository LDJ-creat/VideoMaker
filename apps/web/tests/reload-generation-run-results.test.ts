import { describe, expect, it, vi } from "vitest";

import { fixtureGenerationPlan } from "@/fixtures";
import type { GenerationResponse } from "@/lib/apiClient";
import {
  applyGenerationRunDetail,
  applyLatestGenerationPlans,
  fetchGenerationPlanWithRetry,
  fetchGenerationRunPlans,
  generationRunPlansAreLoaded,
  mergeActiveGenerationsByVariant,
  pickPreferredGenerationEntry,
  reloadGenerationRunPlansWithRetry,
  type ActiveGenerationEntry,
} from "@/lib/reloadGenerationRunResults";

const entries: ActiveGenerationEntry[] = [
  {
    generationId: "gen-a",
    variant: "high_click",
    taskId: "task-a",
    label: "高点击版",
  },
  {
    generationId: "gen-b",
    variant: "high_conversion",
    taskId: "task-b",
    label: "高转化版",
  },
];

describe("reloadGenerationRunResults", () => {
  it("detects when active run plans are missing from cache", () => {
    expect(
      generationRunPlansAreLoaded(entries, {
        "gen-old": fixtureGenerationPlan,
      }),
    ).toBe(false);
    expect(
      generationRunPlansAreLoaded(entries, {
        "gen-a": fixtureGenerationPlan,
        "gen-b": fixtureGenerationPlan,
      }),
    ).toBe(true);
  });

  it("retries until all generation plans are available", async () => {
    vi.useFakeTimers();
    const fetchGeneration = vi
      .fn()
      .mockRejectedValueOnce(new Error("not ready"))
      .mockResolvedValueOnce({
        ...fixtureGenerationPlan,
        id: "gen-a",
      } satisfies GenerationResponse)
      .mockResolvedValue({
        ...fixtureGenerationPlan,
        id: "gen-b",
      } satisfies GenerationResponse);

    const promise = reloadGenerationRunPlansWithRetry(
      entries,
      fetchGeneration,
      { maxAttempts: 3, delayMs: 1000 },
    );
    await vi.advanceTimersByTimeAsync(1000);
    const plans = await promise;

    expect(plans?.["gen-a"]?.id).toBe("gen-a");
    expect(plans?.["gen-b"]?.id).toBe("gen-b");
    expect(fetchGeneration).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("returns null when plans never become ready", async () => {
    vi.useFakeTimers();
    const fetchGeneration = vi.fn().mockRejectedValue(new Error("not ready"));
    const promise = reloadGenerationRunPlansWithRetry(
      [entries[0]!],
      fetchGeneration,
      { maxAttempts: 2, delayMs: 500 },
    );
    await vi.advanceTimersByTimeAsync(1000);
    await expect(promise).resolves.toBeNull();
    vi.useRealTimers();
  });

  it("fetchGenerationRunPlans requires every entry to resolve", async () => {
    const fetchGeneration = vi
      .fn()
      .mockResolvedValueOnce({ ...fixtureGenerationPlan, id: "gen-a" })
      .mockRejectedValueOnce(new Error("missing"));

    await expect(
      fetchGenerationRunPlans(entries, fetchGeneration),
    ).resolves.toBeNull();
  });

  it("applyLatestGenerationPlans hydrates active run entries from latest snapshot", () => {
    const setVariantPlans = vi.fn();
    const setGenerationId = vi.fn();
    const setGenerationPlan = vi.fn();
    const setActiveVariantGenerationId = vi.fn();
    const setGapReport = vi.fn();
    const setGapApiPending = vi.fn();
    const setActiveGenerations = vi.fn();
    const setRenderVideoByGenerationId = vi.fn();

    const plan = {
      ...fixtureGenerationPlan,
      id: "gen-a",
      variant: "high_click",
    } satisfies GenerationResponse;

    const applied = applyLatestGenerationPlans(
      {
        generations: [
          {
            generationId: "gen-a",
            variant: "high_click",
            status: "succeeded",
            taskId: "task-a",
            plan,
          },
        ],
      },
      entries.slice(0, 1),
      {
        setVariantPlans,
        setGenerationId,
        setGenerationPlan,
        setActiveVariantGenerationId,
        setGapReport,
        setGapApiPending,
        setActiveGenerations,
        setRenderVideoByGenerationId,
      },
    );

    expect(applied).toBe(true);
    expect(setGenerationId).toHaveBeenCalledWith("gen-a");
    expect(setGenerationPlan).toHaveBeenCalledWith(plan);
  });

  it("fetchGenerationPlanWithRetry waits until timeline is available", async () => {
    vi.useFakeTimers();
    const fetchGeneration = vi
      .fn()
      .mockResolvedValueOnce({
        ...fixtureGenerationPlan,
        id: "gen-fork",
        timeline: undefined,
      } as unknown as GenerationResponse)
      .mockResolvedValueOnce({
        ...fixtureGenerationPlan,
        id: "gen-fork",
      } satisfies GenerationResponse);

    const promise = fetchGenerationPlanWithRetry("gen-fork", fetchGeneration, {
      maxAttempts: 3,
      delayMs: 500,
    });
    await vi.advanceTimersByTimeAsync(500);
    const plan = await promise;

    expect(plan?.id).toBe("gen-fork");
    expect(plan?.timeline).toBeTruthy();
    expect(fetchGeneration).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("mergeActiveGenerationsByVariant keeps newest entry per variant", () => {
    const merged = mergeActiveGenerationsByVariant(
      [
        {
          generationId: "gen-old",
          variant: "high_conversion",
          taskId: "task-old",
          label: "高转化版",
        },
      ],
      [
        {
          generationId: "gen-fork",
          variant: "high_conversion",
          taskId: "task-fork",
          label: "高转化版",
        },
      ],
    );
    expect(merged).toHaveLength(1);
    expect(merged[0]?.generationId).toBe("gen-fork");
  });

  it("pickPreferredGenerationEntry prefers revise task id", () => {
    const picked = pickPreferredGenerationEntry(
      [
        {
          generationId: "gen-a",
          variant: "high_click",
          taskId: "task-a",
          plan: fixtureGenerationPlan,
        },
        {
          generationId: "gen-fork",
          variant: "high_conversion",
          taskId: "task-fork",
          plan: { ...fixtureGenerationPlan, id: "gen-fork", variant: "high_conversion" },
        },
      ],
      { taskId: "task-fork" },
    );
    expect(picked?.generationId).toBe("gen-fork");
  });

  it("pickPreferredGenerationEntry matches awaiting_review fork without plan", () => {
    const picked = pickPreferredGenerationEntry(
      [
        {
          generationId: "gen-source",
          variant: "high_conversion",
          taskId: "task-source",
          status: "succeeded",
          plan: fixtureGenerationPlan,
        },
        {
          generationId: "gen-fork",
          variant: "high_conversion",
          taskId: "task-fork",
          status: "awaiting_review",
        },
      ],
      { taskId: "task-fork" },
    );
    expect(picked?.generationId).toBe("gen-fork");
  });

  it("applyGenerationRunDetail hydrates all variants and prefers succeeded plan", () => {
    const setVariantPlans = vi.fn();
    const setGenerationId = vi.fn();
    const setGenerationPlan = vi.fn();
    const setActiveVariantGenerationId = vi.fn();
    const setGapReport = vi.fn();
    const setGapApiPending = vi.fn();
    const setActiveGenerations = vi.fn();
    const setRenderVideoByGenerationId = vi.fn();

    const succeededPlan = {
      ...fixtureGenerationPlan,
      id: "gen-b",
      variant: "high_conversion",
    } satisfies GenerationResponse;

    const applied = applyGenerationRunDetail(
      {
        generations: [
          {
            generationId: "gen-a",
            variant: "high_click",
            status: "failed",
            taskId: "task-a",
          },
          {
            generationId: "gen-b",
            variant: "high_conversion",
            status: "succeeded",
            plan: succeededPlan,
          },
        ],
      },
      {
        setVariantPlans,
        setGenerationId,
        setGenerationPlan,
        setActiveVariantGenerationId,
        setGapReport,
        setGapApiPending,
        setActiveGenerations,
        setRenderVideoByGenerationId,
      },
    );

    expect(applied).toHaveLength(2);
    expect(setActiveGenerations).toHaveBeenCalledWith([
      expect.objectContaining({
        generationId: "gen-a",
        variant: "high_click",
        status: "failed",
        taskId: "task-a",
      }),
      expect.objectContaining({
        generationId: "gen-b",
        variant: "high_conversion",
        status: "succeeded",
      }),
    ]);
    expect(setGenerationId).toHaveBeenCalledWith("gen-b");
    expect(setGenerationPlan).toHaveBeenCalledWith(succeededPlan);
    expect(setVariantPlans).toHaveBeenCalledWith({
      "gen-b": succeededPlan,
    });
  });
});
