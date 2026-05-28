export const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;

export function validateHttpUrl(url: string): string | null {
  const trimmed = url.trim();
  if (!trimmed) {
    return "请输入视频链接";
  }
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return "仅支持 http 或 https 链接";
    }
    return null;
  } catch {
    return "链接格式无效";
  }
}

export function validateUploadSize(file: File): string | null {
  if (file.size > MAX_UPLOAD_BYTES) {
    return `文件超过 ${Math.round(MAX_UPLOAD_BYTES / (1024 * 1024))}MB 限制`;
  }
  return null;
}
