export const PLACEHOLDER_NAME_MAX_CHARS = 5;

export function placeholderDisplayName(
  value: string,
  maxChars: number = PLACEHOLDER_NAME_MAX_CHARS,
): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "未命名";
  }
  const chars = [...trimmed];
  if (chars.length <= maxChars) {
    return trimmed;
  }
  return chars.slice(0, maxChars).join("");
}
