import type { CompletionAction } from "@videomaker/contracts";
import { describe, expect, it } from "vitest";

import { resolveCompletionProviderChain } from "@/features/structure-migration/resolveCompletionProviderChain";

describe("resolveCompletionProviderChain", () => {
  it("returns stock then hyperframes for source_then_polish", () => {
    const actions: CompletionAction[] = [
      {
        id: "action-slot-1",
        slotId: "slot-1",
        provider: "stock_media_search",
        strategy: "stock_media_search",
        completionMode: "source_then_polish",
        reason: "stock",
        outputRef: "generated/action-slot-1.mp4",
      },
      {
        id: "action-slot-1-finish",
        slotId: "slot-1",
        provider: "hyperframes_material",
        strategy: "hyperframes_material",
        completionMode: "source_then_polish",
        reason: "finish",
        outputRef: "generated/action-slot-1-finish.mp4",
      },
    ];
    const chain = resolveCompletionProviderChain(actions, "slot-1");
    expect(chain).toEqual(["stock_media_search", "hyperframes_material"]);
  });
});
