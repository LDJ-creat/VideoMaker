import type { ToolError } from "@videomaker/contracts";

import type { FormattedTaskError } from "@/lib/formatTaskError";

function validationDetailsText(error: ToolError): string | undefined {
  const details = error.details;
  if (!details || typeof details !== "object") return undefined;

  const validationErrors = (details as { validationErrors?: unknown }).validationErrors;
  if (!Array.isArray(validationErrors) || validationErrors.length === 0) {
    return undefined;
  }

  return validationErrors
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const entry = item as { path?: unknown; message?: unknown; validator?: unknown };
        const path = typeof entry.path === "string" ? entry.path : "$";
        const message = typeof entry.message === "string" ? entry.message : String(item);
        const validator =
          typeof entry.validator === "string" ? ` (${entry.validator})` : "";
        return `${path}: ${message}${validator}`;
      }
      return String(item);
    })
    .join("\n");
}

export function formatP1TaskError(error: ToolError): FormattedTaskError | null {
  switch (error.code) {
    case "gateway_not_configured":
      return {
        title: "模型服务未配置",
        hint: "请在项目列表页「模型服务」面板填写并保存 text/image 等配置（默认 Live；冒烟可设 VIDEOMAKER_FIXTURE_MODE=true）。",
        technical: error.message,
      };
    case "video_quota_exceeded":
      return {
        title: "生视频配额已用完",
        hint: "该结构槽位已用完视频生成配额（默认每槽 1 次），可改用图片素材或 HyperFrames 动效。",
        technical: error.message,
      };
    case "video_generation_failed":
      return {
        title: "AI 视频生成失败",
        hint:
          error.message?.includes("404")
            ? "视频 API 返回 404：请确认模型服务中「视频」Provider 的 Base URL 为 DashScope，且模型为 Wan 视频模型（如 wan2.6-t2v / wan2.6-i2v-flash），不要使用生图模型。"
            : "请检查视频 Provider 配置、API Key 与模型名称，或在环境变量中设置 VIDEOMAKER_VIDEO_GEN_FALLBACK=image_generation 启用降级。",
        technical: error.message,
      };
    case "generation_failed":
      if (error.message && error.message !== "Worker task failed") {
        return {
          title: "生成任务失败",
          hint: "请查看下方技术详情，修正配置后点击重试。",
          technical: error.message,
        };
      }
      return null;
    case "hyperframes_missing":
      return {
        title: "HyperFrames 未安装",
        hint: "未安装 HyperFrames CLI，包装片段将跳过渲染。请安装后重试。",
        technical: error.message,
      };
    case "LLMValidationError":
      return {
        title: "AI 输出格式异常",
        hint: "模型返回的内容未通过结构校验，可点击重试。详情见下方校验项；完整原始输出见样例 analysis 目录下的 structure-agent-failure.json。",
        technical: validationDetailsText(error) ?? error.message,
      };
    default:
      if (
        error.code.includes("validation") ||
        error.code.includes("schema") ||
        error.message?.toLowerCase().includes("schema")
      ) {
        return {
          title: "AI 输出格式异常",
          hint: "模型返回的内容未通过结构校验，可点击重试。",
          technical: error.message,
        };
      }
      return null;
  }
}
