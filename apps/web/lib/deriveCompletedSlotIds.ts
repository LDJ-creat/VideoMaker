import type { CompletionAction } from "@videomaker/contracts";

import { normalizeMigrationSlotId } from "@/lib/migrationSlotId";

export function deriveCompletedSlotIds(
  completionActions: CompletionAction[],
  completedActionIds: string[] | undefined,
): Set<string> {
  const completed = new Set<string>();
  if (!completedActionIds?.length) {
    return completed;
  }
  const idSet = new Set(completedActionIds);
  for (const action of completionActions) {
    if (!idSet.has(action.id)) continue;
    const normalized = normalizeMigrationSlotId(action.slotId);
    if (normalized) {
      completed.add(normalized);
    }
  }
  return completed;
}
