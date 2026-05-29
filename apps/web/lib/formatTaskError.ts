import type { ToolError } from "@videomaker/contracts";

import { formatP1TaskError } from "@/lib/formatTaskError.p1";

export type FormattedTaskError = {
  title: string;
  hint?: string;
  technical?: string;
};

export function formatTaskError(error: ToolError | undefined): FormattedTaskError | null {
  if (!error) return null;

  const stderr =
    typeof error.details === "object" &&
    error.details !== null &&
    "stderr" in error.details &&
    typeof error.details.stderr === "string"
      ? error.details.stderr.trim()
      : undefined;

  const platform =
    typeof error.details === "object" &&
    error.details !== null &&
    "platform" in error.details &&
    typeof error.details.platform === "string"
      ? error.details.platform
      : undefined;
  const platformName =
    platform === "douyin"
      ? "抖音"
      : platform === "bilibili"
        ? "B站"
        : platform === "youtube"
          ? "YouTube"
          : platform;

  const p1Error = formatP1TaskError(error);
  if (p1Error) return p1Error;

  switch (error.code) {
    case "ytdlp_cookies_required":
      return {
        title: platformName
          ? `下载失败：${platformName} 需要有效 Cookie`
          : "下载失败：需要有效的 Cookie",
        hint: platformName
          ? `当前全局 Cookie 可能未包含 ${platformName}、已过期或未登录。请在浏览器登录 ${platformName} 后重新导出 cookies.txt，在本页选择「合并上传」后重试（不会影响其他平台已保存的 Cookie）。`
          : "请在浏览器登录目标平台后导出 cookies.txt，在本页「平台 Cookie」处合并上传后重试 URL 导入。",
        technical: stderr,
      };
    case "fast_whisper_missing":
      return {
        title: "转写失败：未安装 faster-whisper",
        hint:
          "在 services/api 目录执行：uv pip install --python .venv-dev faster-whisper，然后重启 API。",
        technical: stderr,
      };
    case "fast_whisper_model_unavailable":
      return {
        title: "转写失败：Whisper 模型下载超时",
        hint:
          "首次转写需从 Hugging Face 下载模型。可设镜像 HF_ENDPOINT=https://hf-mirror.com 或 HF_TOKEN；或设 VIDEOMAKER_SKIP_WHISPER=1 跳过转写继续分析；模型下载成功后重试即可。",
        technical: stderr ?? error.message,
      };
    case "fast_whisper_failed":
      return {
        title: "转写失败",
        hint: "可设置 VIDEOMAKER_SKIP_WHISPER=1 跳过转写，先完成结构分析演示。",
        technical: stderr ?? error.message,
      };
    case "ytdlp_missing":
      return {
        title: "下载失败：未安装 yt-dlp",
        hint: "请在运行 API 的机器上安装 yt-dlp 并加入 PATH。",
        technical: stderr,
      };
    case "ytdlp_unsupported_url":
      return {
        title: "下载失败：无法解析该视频链接",
        hint: "请确认链接为可公开访问的单条视频页面，或改用本地上传样例。",
        technical: stderr,
      };
    default: {
      const cookieHint =
        stderr?.toLowerCase().includes("cookie") ||
        error.message?.toLowerCase().includes("cookie");
      if (cookieHint) {
        return {
          title: "下载失败：可能需要有效的 Cookie",
          hint:
            "请用扩展导出 cookies.txt，在本页「平台 Cookie」处上传后重试 URL 导入。",
          technical: stderr ?? error.message,
        };
      }
      return {
        title: error.message || "任务失败",
        hint:
          error.code === "url_import_failed" || error.code === "sample_analysis_failed"
            ? "可点击「重试」从上次进度继续；若仍失败请查看下方技术详情或改用本地上传。"
            : undefined,
        technical: stderr ?? error.message,
      };
    }
  }
}
