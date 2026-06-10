export type TaskMaterialProgressHint = {
  slotId: string | null;
  actionLabel: string | null;
  summary: string | null;
};

const COMPLETING_SLOT = /Completing slot\s+(\S+)/i;
const AUTHORING_HF = /Authoring HyperFrames material spec/i;
const HF_READY = /HyperFrames material ready for slot\s+(\S+)/i;

export function parseTaskMaterialProgress(
  message: string | undefined,
): TaskMaterialProgressHint {
  if (!message) {
    return { slotId: null, actionLabel: null, summary: null };
  }

  const completing = message.match(COMPLETING_SLOT);
  if (completing) {
    const slotId = completing[1] ?? null;
    return {
      slotId,
      actionLabel: "素材补全",
      summary: slotId ? `正在处理：${slotId} · 素材补全` : null,
    };
  }

  if (AUTHORING_HF.test(message)) {
    return {
      slotId: null,
      actionLabel: "HyperFrames 包装",
      summary: "正在处理：HyperFrames 包装分镜",
    };
  }

  const hfReady = message.match(HF_READY);
  if (hfReady) {
    const slotId = hfReady[1] ?? null;
    return {
      slotId,
      actionLabel: "HyperFrames 渲染",
      summary: slotId ? `正在处理：${slotId} · HyperFrames 渲染` : null,
    };
  }

  return { slotId: null, actionLabel: null, summary: null };
}
