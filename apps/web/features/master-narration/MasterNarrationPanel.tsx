"use client";

import type { GapReport, GenerationPlan, VideoStructure } from "@videomaker/contracts";
import { Clock, Layers, Mic } from "lucide-react";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  buildSlotMigrationRowsFromPlan,
  migrationSummaryFromRows,
} from "@/features/structure-migration/buildSlotMigrationRows";
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
  structure?: VideoStructure | null;
  gapReport?: GapReport | null;
};

export function MasterNarrationPanel({
  plan,
  structure,
  gapReport,
}: MasterNarrationPanelProps) {
  const master = resolveMasterNarration(plan);
  const scenes = [...plan.storyboard].sort(
    (left, right) => left.startSec - right.startSec,
  );
  const scriptedScenes = scenes.filter((scene) => scene.script.trim());
  const estimatedSec = estimateSpeechDurationSec(master);
  const derivedFallback =
    !plan.masterNarration?.trim() && master === deriveMasterFromStoryboard(plan.storyboard);

  const migrationRows = useMemo(() => {
    if (!structure) return [];
    return buildSlotMigrationRowsFromPlan(structure, plan, gapReport ?? null);
  }, [gapReport, plan, structure]);

  const migrationBySlot = useMemo(
    () => new Map(migrationRows.map((row) => [row.slotId, row])),
    [migrationRows],
  );

  const migrationSummary = migrationRows.length
    ? migrationSummaryFromRows(migrationRows)
    : null;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5 text-primary" aria-hidden />
                全片拆解
              </CardTitle>
              <CardDescription>
                变体 {getVariantLabel(plan.variant)} · 样例结构 → Brief → 素材补全 → 分镜口播
                {migrationSummary ? ` · ${migrationSummary}` : ""}
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
            <div className="space-y-2">
              <p className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <Mic className="h-3.5 w-3.5" aria-hidden />
                全片口播稿
              </p>
              <div
                className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-base leading-relaxed tracking-wide"
                data-testid="master-narration-text"
              >
                {master}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">暂无全片口播文本。</p>
          )}

          <div className="space-y-3 border-t border-border pt-4">
            <div>
              <p className="text-sm font-medium">槽位拆解</p>
              <p className="text-xs text-muted-foreground">
                每个结构槽位的迁移意图、视觉素材来源与分镜口播。
              </p>
            </div>
            {scenes.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无分镜数据。</p>
            ) : (
              scenes.map((scene, index) => {
                const migration = migrationBySlot.get(scene.slotId);
                return (
                  <StoryboardSceneCard
                    key={scene.id}
                    scene={scene}
                    index={index}
                    master={master}
                    media={resolveStoryboardSceneMedia(plan, scene)}
                    roleLabel={migration?.roleLabel}
                    visualIntent={migration?.visualIntent ?? scene.visual}
                    scriptIntent={migration?.scriptIntent}
                    userAssetId={migration?.userAssetId}
                    userAssetSummary={migration?.userAssetSummary}
                    gapSummary={migration?.gapSummary}
                    completionProvider={migration?.completionProvider}
                  />
                );
              })
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
