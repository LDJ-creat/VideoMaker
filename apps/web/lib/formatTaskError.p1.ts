import type { ToolError } from "@videomaker/contracts";

import type { FormattedTaskError } from "@/lib/formatTaskError";

export function formatP1TaskError(error: ToolError): FormattedTaskError | null {
  switch (error.code) {
    case "gateway_not_configured":
      return {
        title: "模型服务未配置",
        hint: "请在服务端配置模型 API 环境变量（TEXT_API_KEY、IMAGE_API_KEY 等）后重启 API。",
        technical: error.message,
      };
    case "video_quota_exceeded":
      return {
        title: "生视频配额已用完",
        hint: "本条生成已用完 1 次生视频配额，可改用图片素材或重试其他变体。",
        technical: error.message,
      };
    case "hyperframes_missing":
      return {
        title: "HyperFrames 未安装",
        hint: "未安装 HyperFrames CLI，包装片段将跳过渲染。请安装后重试。",
        technical: error.message,
      };
    case "LLMValidationError":
      return {
        title: "AI 输出格式异常",
        hint: "模型返回的内容未通过结构校验，可点击重试。",
        technical: error.message,
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
