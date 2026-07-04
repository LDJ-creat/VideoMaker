import type { AgentRunLog } from "@videomaker/contracts";

function parseInputSummary(summary: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(summary) as unknown;
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function failureCategory(errors: string[]): string {
  const joined = errors.join(" ").toLowerCase();
  if (joined.includes("connection closed") || joined.includes("connection reset")) {
    return "session 连接失败";
  }
  if (joined.includes("mcp") || joined.includes("tool list")) {
    return "MCP 工具未挂载";
  }
  if (joined.includes("acp_author_spec_invalid") || joined.includes("turn")) {
    return "lint 修复轮次耗尽";
  }
  if (joined.includes("sandbox") || joined.includes("path escape")) {
    return "沙箱路径违规";
  }
  return "ACP 作者失败";
}

export function resolveMaterialAuthorFailureSummary(
  agentRuns: AgentRunLog[] | null | undefined,
  slotId: string,
): string | null {
  if (!agentRuns?.length) return null;

  const run = agentRuns.find((entry) => {
    if (entry.agentName !== "material_author" || entry.outputValid !== false) {
      return false;
    }
    const summary = parseInputSummary(entry.inputSummary ?? "");
    return summary?.slotId === slotId;
  });

  if (!run) return null;

  const errors = run.validationErrors ?? [];
  const category = failureCategory(errors);
  const detail = errors[0]?.slice(0, 160) ?? "未知错误";
  return `${category}: ${detail}`;
}
