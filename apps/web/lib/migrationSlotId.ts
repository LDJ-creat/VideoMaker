/** Strip material suffixes so slot-1-finish maps to structure slot slot-1. */
export function normalizeMigrationSlotId(
  slotId: string | null | undefined,
): string | null {
  if (!slotId) return null;
  const trimmed = slotId.trim();
  if (!trimmed) return null;
  return trimmed.replace(/-(?:finish|ken-burns)$/i, "");
}
