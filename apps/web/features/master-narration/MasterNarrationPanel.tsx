"use client";

import type { GenerationPlan } from "@videomaker/contracts";
import { Clock, Mic, SplitSquareHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  deriveMasterFromStoryboard,
  estimateSpeechDurationSec,
  resolveMasterNarration,
} from "@/features/master-narration/resolveMasterNarration";
import { resolveStoryboardSceneMedia } from "@/features/master-narration/resolveStoryboardSceneMedia";
import { StoryboardSceneCard } from "@/features/master-narration/StoryboardSceneCard";
import { getVariantLabel } from "@/lib/variantRegistry";

type MasterNarrationPanelProps = {
  plan: GenerationPlan;
};

export function MasterNarrationPanel({ plan }: MasterNarrationPanelProps) {
  const master = resolveMasterNarration(plan);
  const scenes = [...plan.storyboard].sort(
    (left, right) => left.startSec - right.startSec,
  );
  const scriptedScenes = scenes.filter((scene) => scene.script.trim());
  const estimatedSec = estimateSpeechDurationSec(master);
  const derivedFallback =
    !plan.masterNarration?.trim() && master === deriveMasterFromStoryboard(plan.storyboard);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Mic className="h-5 w-5 text-primary" aria-hidden />
                全片口播
              </CardTitle>
              <CardDescription>
                变体 {getVariantLabel(plan.variant)} · 全片叙事层（TTS / 字幕源）
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{master.length} 字</Badge>
              <Badge variant="outline" className="gap-1">
                <Clock className="h-3 w-3" aria-hidden />
                约 {estimatedSec}s
              </Badge>
              <Badge variant="outline">
                {scriptedScenes.length}/{scenes.length} 段有口播
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {derivedFallback ? (
            <p className="text-xs text-muted-foreground">
              该计划未单独保存 masterNarration，当前文本由分镜口播拼接展示。
            </p>
          ) : null}

          {master ? (
            <div
              className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-base leading-relaxed tracking-wide"
              data-testid="master-narration-text"
            >
              {master}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">暂无全片口播文本。</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <SplitSquareHorizontal className="h-4 w-4 text-primary" aria-hidden />
            分镜预览
          </CardTitle>
          <CardDescription>
            各槽位画面素材与口播切分；左侧为分镜视频/图片，右侧为 TTS 与字幕使用的 script。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {scenes.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无分镜数据。</p>
          ) : (
            scenes.map((scene, index) => (
              <StoryboardSceneCard
                key={scene.id}
                scene={scene}
                index={index}
                master={master}
                media={resolveStoryboardSceneMedia(plan, scene)}
              />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
