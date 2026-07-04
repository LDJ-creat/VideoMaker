import type { CompositionAuthorBrief } from "@videomaker/contracts";

const MODE_LABELS: Record<string, string> = {
  hf_native: "HF 全屏生成",
  source_then_polish: "底片 + HF 润色",
  polish_only: "仅润色 overlay",
  packaging_only: "包装专用",
};

const LAYOUT_LABELS: Record<string, string> = {
  center: "主信息居中",
  lower_third: "下方 1/3 overlay",
  upper_third: "上方 1/3 overlay",
};

const TEMPLATE_LABELS: Record<string, string> = {
  composition: "composition 自定义",
  "benefit-card": "benefit-card 模板",
  "title-lower-third": "title-lower-third 模板",
  "ken-burns": "ken-burns 模板",
};

export function compositionModeLabel(mode: string | undefined): string | null {
  const key = String(mode ?? "").trim();
  if (!key) return null;
  return MODE_LABELS[key] ?? key;
}

export function compositionLayoutLabel(anchor: string | undefined): string | null {
  const key = String(anchor ?? "").trim();
  if (!key) return null;
  return LAYOUT_LABELS[key] ?? key;
}

export function compositionTemplateLabel(template: string | undefined): string | null {
  const key = String(template ?? "").trim();
  if (!key) return null;
  return TEMPLATE_LABELS[key] ?? key;
}

export function formatCompositionBriefMeta(brief: CompositionAuthorBrief): string[] {
  const parts: string[] = [];
  const mode = compositionModeLabel(brief.mode);
  if (mode) parts.push(mode);
  const layout = compositionLayoutLabel(brief.layoutAnchor);
  if (layout) parts.push(layout);
  const template = compositionTemplateLabel(brief.templatePreference);
  if (template) parts.push(template);
  return parts;
}

export function hasCompositionDesignContent(input: {
  brief?: CompositionAuthorBrief | null;
  finishIntent?: string | null;
  visualDirection?: string | null;
}): boolean {
  return Boolean(
    input.brief?.authorPrompt?.trim() ||
      input.finishIntent?.trim() ||
      (input.visualDirection?.trim() &&
        input.visualDirection !== input.brief?.authorPrompt?.trim()),
  );
}
