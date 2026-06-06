export const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;

export const ASSET_VIDEO_MAX_BYTES = 50 * 1024 * 1024;
export const ASSET_IMAGE_MAX_BYTES = 30 * 1024 * 1024;
export const ASSET_TEXT_MAX_BYTES = 512 * 1024;

function inferAssetUploadType(file: File): "video" | "image" | "text" | null {
  const mime = file.type.toLowerCase();
  const name = file.name.toLowerCase();
  if (mime.startsWith("video/")) {
    return "video";
  }
  if (mime.startsWith("image/")) {
    return "image";
  }
  if (
    mime.startsWith("text/") ||
    name.endsWith(".txt") ||
    name.endsWith(".md") ||
    name.endsWith(".markdown")
  ) {
    return "text";
  }
  return null;
}

export function validateAssetUploadSize(file: File): string | null {
  const assetType = inferAssetUploadType(file);
  if (assetType === null) {
    return "不支持的文件类型，请上传视频、图片或文案 (.txt/.md)";
  }
  const limits: Record<"video" | "image" | "text", number> = {
    video: ASSET_VIDEO_MAX_BYTES,
    image: ASSET_IMAGE_MAX_BYTES,
    text: ASSET_TEXT_MAX_BYTES,
  };
  const limit = limits[assetType];
  if (file.size > limit) {
    const limitMb = Math.max(1, Math.round(limit / (1024 * 1024)));
    const label =
      assetType === "video" ? "视频" : assetType === "image" ? "图片" : "文案";
    return `${label}文件超过 ${limitMb}MB 限制（与直连多模态资产理解上限一致）`;
  }
  return null;
}

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
