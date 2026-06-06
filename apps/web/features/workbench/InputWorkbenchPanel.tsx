"use client";

import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  BriefEditor,
  type BriefEditorHandle,
} from "@/features/project-input/BriefEditor";
import {
  GenerationConfigPanel,
  type GenerationConfigPanelHandle,
} from "@/features/project-input/GenerationConfigPanel";
import {
  InputWizardAdvanced,
  InputWizardLayout,
  InputWizardPrimaryGrid,
  InputWizardSecondaryGrid,
  InputWizardSection,
} from "@/features/project-input/InputWizardLayout";
import { SampleInputPanel } from "@/features/project-input/SampleInputPanel";
import { SampleSelectionPanel } from "@/features/project-input/SampleSelectionPanel";
import { KnowledgeSelectionPanel } from "@/features/knowledge/KnowledgeSelectionPanel";
import type {
  ActiveSampleSummary,
  ProjectAsset,
  UserBriefRequest,
} from "@/lib/apiClient";
import { listKnowledgeEntries, saveBrief } from "@/lib/apiClient";
import type { DurationTarget } from "@videomaker/contracts";

type InputWorkbenchPanelProps = {
  projectId: string;
  samples: ActiveSampleSummary[];
  assets: ProjectAsset[];
  activeSample?: ActiveSampleSummary | null;
  selectedSampleId?: string | null;
  savedBrief?: UserBriefRequest | null;
  selectedVariantIds: string[];
  busy?: boolean;
  onSavedBrief: (brief: UserBriefRequest) => void;
  onVariantChange: (variantIds: string[]) => void;
  onTaskStarted: (taskId: string, sampleId: string) => void;
  onBatchAnalysisStarted: (
    tasks: Array<{ sampleId: string; taskId: string }>,
    maxConcurrent: number,
  ) => void;
  onSampleReady: (sampleId: string) => void;
  onSelectSample: (sampleId: string) => void;
  onSampleChanged: () => void;
  onAssetsChanged: () => void;
  onKnowledgeApplied: () => void;
  onSelectionChanged: () => void;
};

export type InputWorkbenchPanelHandle = {
  getBrief: () => UserBriefRequest;
  getDurationTarget: () => DurationTarget | undefined;
};

function step3StorageKey(projectId: string): string {
  return `vm-input-step3-expanded-${projectId}`;
}

export const InputWorkbenchPanel = forwardRef<
  InputWorkbenchPanelHandle,
  InputWorkbenchPanelProps
>(function InputWorkbenchPanel(
  {
  projectId,
  samples,
  assets,
  activeSample,
  selectedSampleId,
  savedBrief,
  selectedVariantIds,
  busy = false,
  onSavedBrief,
  onVariantChange,
  onTaskStarted,
  onBatchAnalysisStarted,
  onSampleReady,
  onSelectSample,
  onSampleChanged,
  onAssetsChanged,
  onKnowledgeApplied,
  onSelectionChanged,
  },
  ref,
) {
  const briefEditorRef = useRef<BriefEditorHandle>(null);
  const generationConfigRef = useRef<GenerationConfigPanelHandle>(null);
  const [hasPublishedKnowledge, setHasPublishedKnowledge] = useState(false);
  const [step3Open, setStep3Open] = useState(false);

  const analyzedCount = useMemo(
    () => samples.filter((sample) => sample.hasStructure).length,
    [samples],
  );

  useEffect(() => {
    try {
      const stored = localStorage.getItem(step3StorageKey(projectId));
      if (stored === "true") setStep3Open(true);
    } catch {
      /* ignore */
    }
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    void listKnowledgeEntries()
      .then(({ data }) => {
        if (!cancelled) {
          setHasPublishedKnowledge(data.entries.length > 0);
        }
      })
      .catch(() => {
        if (!cancelled) setHasPublishedKnowledge(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useImperativeHandle(
    ref,
    () => ({
      getBrief: () => briefEditorRef.current?.getBrief() ?? { sellingPoints: [], mustMention: [], avoidMention: [] },
      getDurationTarget: () => generationConfigRef.current?.getDurationTarget(),
    }),
    [],
  );

  const handleSaveBrief = async () => {
    const brief = briefEditorRef.current?.getBrief();
    if (!brief) return;
    const durationTarget = generationConfigRef.current?.getDurationTarget();
    if (durationTarget) {
      brief.durationTarget = durationTarget;
    }
    await saveBrief(projectId, brief);
    onSavedBrief(brief);
    try {
      localStorage.setItem(step3StorageKey(projectId), "true");
      setStep3Open(true);
    } catch {
      /* ignore */
    }
  };

  return (
    <InputWizardLayout>
      <InputWizardPrimaryGrid>
        <InputWizardSection
          step={1}
          title="样例视频"
          description="支持一次上传多个视频；链接导入由服务端下载。"
          className="h-full"
        >
          <SampleInputPanel
            embedded
            projectId={projectId}
            samples={samples}
            activeSample={activeSample}
            selectedSampleId={selectedSampleId}
            onTaskStarted={onTaskStarted}
            onBatchAnalysisStarted={onBatchAnalysisStarted}
            onSampleReady={onSampleReady}
            onSelectSample={onSelectSample}
            onSampleChanged={onSampleChanged}
          />
        </InputWizardSection>

        <InputWizardSection
          step={2}
          title="创作 Brief"
          description="描述创作意图与约束；系统会结合样例结构统一理解。"
          className="h-full"
          actionSlot={
            <Button type="button" size="sm" onClick={() => void handleSaveBrief()}>
              保存 Brief
            </Button>
          }
        >
          <BriefEditor
            ref={briefEditorRef}
            embedded
            showSaveButton={false}
            projectId={projectId}
            initialBrief={savedBrief}
            getDurationTarget={() => generationConfigRef.current?.getDurationTarget()}
            onSaved={onSavedBrief}
          />
        </InputWizardSection>
      </InputWizardPrimaryGrid>

      <InputWizardAdvanced
        title="Step 3 · 素材与生成配置"
        defaultOpen={step3Open}
        testId="input-wizard-step-3"
      >
        <GenerationConfigPanel
          ref={generationConfigRef}
          projectId={projectId}
          assets={assets}
          initialTarget={savedBrief?.durationTarget}
          selectedVariantIds={selectedVariantIds}
          onVariantChange={onVariantChange}
          variantsDisabled={busy}
          onAssetsChanged={onAssetsChanged}
        />
      </InputWizardAdvanced>

      <InputWizardSecondaryGrid>
        <InputWizardAdvanced
          title="样例选择"
          defaultOpen={analyzedCount > 0}
          testId="input-wizard-sample-selection"
        >
          <SampleSelectionPanel
            embedded
            projectId={projectId}
            onSelectionChanged={onSelectionChanged}
          />
        </InputWizardAdvanced>

        <InputWizardAdvanced
          title="推荐知识"
          defaultOpen={hasPublishedKnowledge}
          testId="input-wizard-knowledge-selection"
        >
          {hasPublishedKnowledge ? (
            <KnowledgeSelectionPanel
              projectId={projectId}
              onApplied={onKnowledgeApplied}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              暂无已发布知识库条目。完成样例分析并 promote 后即可自动推荐；也可在「知识库」标签页管理。
            </p>
          )}
        </InputWizardAdvanced>
      </InputWizardSecondaryGrid>
    </InputWizardLayout>
  );
});
