const EXACT_MESSAGES: Record<string, string> = {
  "Queued sample analysis": "排队等待开始分析",
  "Queued URL sample import": "排队等待下载样例视频",
  "Queued generation revise": "排队等待改片任务",
  "Sample analysis and structure extraction completed": "样例分析与结构提取已完成",
  "Starting sample analysis": "开始样例分析",
  "Starting sample analysis (resume)": "从 checkpoint 继续样例分析",
  "Resuming sample analysis from checkpoint": "从上次进度继续样例分析",
  "Retry requested, resuming from checkpoint": "正在重试，从 checkpoint 继续",
  "Direct multimodal structure extraction": "直连多模态结构分析中",
  "Direct multimodal structure saved": "直连多模态结构已保存",
  "Validating direct multimodal structure output": "正在校验直连多模态结构输出",
  "Perception complete, preparing structure analysis": "感知阶段完成，准备结构分析",
  "extracting video metadata": "正在提取视频元信息",
  "extracting sample audio": "正在提取样例音频",
  "running whisper transcription": "正在进行语音转写",
  "analyzing audio profile": "正在分析音频画像",
  "detecting video shots": "正在进行镜头切分",
  "skip keyframe extraction (direct multimodal route)": "直连路由跳过关键帧提取",
  "Direct multimodal structure extraction failed": "直连多模态结构分析失败",
  "Extracting video structure": "正在提取视频结构",
  "Sample analysis failed": "样例分析失败",
  "URL import failed": "URL 导入失败",
  "Downloading sample from URL": "正在从链接下载样例",
  "Analysis route changed; restart sample analysis": "分析路径已变更，请重新分析",
};

const PREFIX_MESSAGES: Array<{ prefix: string; label: string }> = [
  { prefix: "Queued generation plan (", label: "排队等待生成计划" },
  { prefix: "(resumed) ", label: "" },
];

export function formatTaskMessage(message: string | undefined | null): string {
  const text = String(message ?? "").trim();
  if (!text) return "处理中…";

  if (EXACT_MESSAGES[text]) {
    return EXACT_MESSAGES[text];
  }

  for (const { prefix, label } of PREFIX_MESSAGES) {
    if (text.startsWith(prefix)) {
      const rest = text.slice(prefix.length);
      if (prefix === "(resumed) ") {
        const resumed = EXACT_MESSAGES[rest] ?? rest;
        return `（已恢复）${resumed}`;
      }
      if (prefix.startsWith("Queued generation plan")) {
        return label;
      }
    }
  }

  if (/[\u4e00-\u9fff]/.test(text)) {
    return text;
  }

  return text;
}
