"use client";

import { useCallback, useEffect, useState } from "react";

import { KnowledgeMarkdownPreview, KnowledgeReasonTags } from "@/features/knowledge/KnowledgeMarkdownPreview";
import {
  isKnowledgeStructureApplyBlockedMessage,
  KNOWLEDGE_STRUCTURE_APPLY_BLOCKED_HINT,
  MAX_KNOWLEDGE_REFERENCE_ENTRIES,
} from "@/features/knowledge/knowledgeMessages";
import {
  formatKnowledgeMatchScore,
  SelectionCandidateZone,
  SelectionCurrentZone,
} from "@/features/project-input/SelectionPanelZones";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { KnowledgeEntry, KnowledgeRecommendation, ProjectKnowledgeSelection } from "@videomaker/contracts";
import {
  applyKnowledgeToProject,
  getKnowledgeEntry,
  getKnowledgeSelection,
  getKnowledgeSkill,
  listKnowledgeEntries,
  listProjectSamples,
  recommendKnowledge,
  resetKnowledgeSelection,
  updateKnowledgeSelection,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

type KnowledgeSelectionPanelProps = {
  projectId: string;
  onApplied?: () => void;
};

function hasAnalyzedRealSampleStructure(
  samples: Array<{ hasStructure: boolean; sourceKind: string }>,
): boolean {
  return samples.some(
    (sample) => sample.hasStructure && sample.sourceKind !== "knowledge",
  );
}

export function KnowledgeSelectionPanel({
  projectId,
  onApplied,
}: KnowledgeSelectionPanelProps) {
  const [selection, setSelection] = useState<ProjectKnowledgeSelection | null>(null);
  const [recommendation, setRecommendation] = useState<KnowledgeRecommendation | null>(null);
  const [primaryEntry, setPrimaryEntry] = useState<KnowledgeEntry | null>(null);
  const [referenceEntries, setReferenceEntries] = useState<KnowledgeEntry[]>([]);
  const [structureApplyBlocked, setStructureApplyBlocked] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const [selectionResult, recommendResult, samplesResult] = await Promise.all([
        getKnowledgeSelection(projectId),
        recommendKnowledge(projectId),
        listProjectSamples(projectId),
      ]);
      const currentSelection = selectionResult.data.selection;
      setSelection(currentSelection);
      setRecommendation(recommendResult.data.recommendation);
      setStructureApplyBlocked(hasAnalyzedRealSampleStructure(samplesResult.data.samples));

      const primaryId =
        currentSelection?.primaryEntryId ??
        recommendResult.data.selection?.primaryEntryId ??
        recommendResult.data.recommendation?.suggestedPrimaryId ??
        null;

      const referenceIds = currentSelection?.referenceEntryIds ?? [];

      if (primaryId) {
        const entryResult = await getKnowledgeEntry(primaryId);
        setPrimaryEntry(entryResult.data);
      } else {
        setPrimaryEntry(null);
      }

      const refEntries = await Promise.all(
        referenceIds.map(async (entryId) => {
          try {
            const result = await getKnowledgeEntry(entryId);
            return result.data;
          } catch {
            return null;
          }
        }),
      );
      setReferenceEntries(refEntries.filter((entry): entry is KnowledgeEntry => entry !== null));
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const persistSelection = async (body: {
    primaryEntryId: string;
    referenceEntryIds: string[];
    applyStructure?: boolean;
  }) => {
    await updateKnowledgeSelection(projectId, {
      primaryEntryId: body.primaryEntryId,
      referenceEntryIds: body.referenceEntryIds,
      applyStructure: body.applyStructure ?? false,
    });
    await refresh();
  };

  const handleSelectPrimary = async (entryId: string) => {
    setLoading(true);
    setStatus(null);
    try {
      const refs = (selection?.referenceEntryIds ?? []).filter((id) => id !== entryId);
      await persistSelection({
        primaryEntryId: entryId,
        referenceEntryIds: refs,
      });
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const toggleReference = async (entryId: string) => {
    if (!selection?.primaryEntryId || entryId === selection.primaryEntryId) {
      return;
    }
    const refs = new Set(selection.referenceEntryIds ?? []);
    if (refs.has(entryId)) {
      refs.delete(entryId);
    } else {
      if (refs.size >= MAX_KNOWLEDGE_REFERENCE_ENTRIES) {
        setStatus(`最多添加 ${MAX_KNOWLEDGE_REFERENCE_ENTRIES} 条参考知识`);
        return;
      }
      refs.add(entryId);
    }
    setLoading(true);
    setStatus(null);
    try {
      await persistSelection({
        primaryEntryId: selection.primaryEntryId,
        referenceEntryIds: Array.from(refs),
      });
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const handleApplyStructure = async (entryId: string) => {
    if (structureApplyBlocked) {
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      await applyKnowledgeToProject(projectId, { entryId, applyStructure: true });
      await refresh();
      onApplied?.();
    } catch (error) {
      const message = getErrorMessage(error);
      setStatus(
        isKnowledgeStructureApplyBlockedMessage(message)
          ? KNOWLEDGE_STRUCTURE_APPLY_BLOCKED_HINT
          : message,
      );
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setLoading(true);
    try {
      await resetKnowledgeSelection(projectId);
      await refresh();
      onApplied?.();
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const activeCandidate = recommendation?.candidates.find(
    (item) => item.entryId === selection?.primaryEntryId,
  );

  const applyStructureDisabled = loading || structureApplyBlocked;
  const applyStructureTitle = structureApplyBlocked
    ? KNOWLEDGE_STRUCTURE_APPLY_BLOCKED_HINT
    : "将知识条目的结构写入项目（无样例分析时可用）";

  return (
    <Card>
      <CardHeader>
        <CardTitle>推荐知识</CardTitle>
        <CardDescription>
          主知识决定生成时的核心参考；参考知识补充额外结构经验（最多{" "}
          {MAX_KNOWLEDGE_REFERENCE_ENTRIES} 条）。系统也会根据 Brief 自动推荐。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && <p className="text-sm text-muted-foreground">加载推荐知识…</p>}

        {structureApplyBlocked && (
          <p className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            {KNOWLEDGE_STRUCTURE_APPLY_BLOCKED_HINT}
          </p>
        )}

        {primaryEntry ? (
          <>
            <SelectionCurrentZone description="生成 Agent 将优先参考以下结构经验">
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  主知识
                </p>
                <div className="rounded-lg border border-primary/25 bg-background/60 p-3">
                  <p className="text-sm">
                    已{selection?.mode === "user_override" ? "手动" : "自动"}选用：
                    <span className="ml-1 font-medium">{primaryEntry.title}</span>
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">{primaryEntry.summary}</p>
                  <KnowledgeReasonTags reasons={activeCandidate?.reasons ?? []} />
                </div>
              </div>

              {referenceEntries.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    参考知识
                  </p>
                  <ul className="space-y-2">
                    {referenceEntries.map((entry) => (
                      <li
                        key={entry.id}
                        className="rounded-lg border border-border/80 bg-background/40 px-3 py-2 text-sm"
                      >
                        <span className="font-medium">{entry.title}</span>
                        <p className="mt-0.5 text-muted-foreground">{entry.summary}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </SelectionCurrentZone>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={loading}
                onClick={() => setExpanded((v) => !v)}
              >
                {expanded
                  ? "收起候选列表"
                  : `查看其他推荐（${recommendation?.candidates.length ?? 0}）`}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={loading}
                onClick={() => void handleReset()}
              >
                恢复自动选用
              </Button>
              {selection?.primaryEntryId && (
                <Button
                  type="button"
                  size="sm"
                  disabled={applyStructureDisabled}
                  title={applyStructureTitle}
                  onClick={() => void handleApplyStructure(selection.primaryEntryId!)}
                >
                  应用为项目结构
                </Button>
              )}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            暂无已发布知识库条目。完成样例分析并 promote 后即可自动推荐。
          </p>
        )}

        {expanded && recommendation && (
          <SelectionCandidateZone
            title="推荐候选"
            count={recommendation.candidates.length}
            onCollapse={() => setExpanded(false)}
          >
            {recommendation.candidates.map((candidate) => {
              const isPrimary = candidate.entryId === selection?.primaryEntryId;
              const isReference = selection?.referenceEntryIds?.includes(candidate.entryId);
              const matchScore = formatKnowledgeMatchScore(candidate.score);
              return (
                <div
                  key={candidate.entryId}
                  className="rounded-lg border border-border/70 bg-background/50 p-3 text-sm"
                >
                  <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{candidate.entry.title}</span>
                    <div className="flex flex-wrap gap-1">
                      {isPrimary && <Badge>主知识</Badge>}
                      {isReference && <Badge variant="outline">参考</Badge>}
                      {matchScore && (
                        <Badge variant="secondary" title="与 Brief / 样例结构的匹配度">
                          匹配 {matchScore}
                        </Badge>
                      )}
                    </div>
                  </div>
                  <p className="text-muted-foreground">{candidate.entry.summary}</p>
                  <KnowledgeReasonTags reasons={candidate.reasons} />
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant={isPrimary ? "default" : "outline"}
                      disabled={loading}
                      onClick={() => void handleSelectPrimary(candidate.entryId)}
                    >
                      {isPrimary ? "当前主知识" : "设为主知识"}
                    </Button>
                    {!isPrimary && (
                      <Button
                        type="button"
                        size="sm"
                        variant={isReference ? "secondary" : "outline"}
                        disabled={loading}
                        onClick={() => void toggleReference(candidate.entryId)}
                      >
                        {isReference ? "取消参考" : "加入参考"}
                      </Button>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={applyStructureDisabled}
                      title={applyStructureTitle}
                      onClick={() => void handleApplyStructure(candidate.entryId)}
                    >
                      应用结构
                    </Button>
                  </div>
                </div>
              );
            })}
          </SelectionCandidateZone>
        )}

        {status && <p className="text-sm text-destructive">{status}</p>}
      </CardContent>
    </Card>
  );
}

type KnowledgeLibraryViewProps = {
  onSelect?: (entryId: string) => void;
};

export function KnowledgeLibraryView({ onSelect }: KnowledgeLibraryViewProps) {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [skillMarkdown, setSkillMarkdown] = useState<string | null>(null);
  const [skillLoading, setSkillLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const loadEntries = useCallback(async () => {
    try {
      const result = await listKnowledgeEntries({ q: query || undefined });
      const nextEntries = result.data.entries;
      setEntries(nextEntries);
      if (nextEntries.length === 0) {
        setSelectedId(null);
        setSkillMarkdown(null);
        return;
      }
      setSelectedId((current) => {
        if (current && nextEntries.some((entry) => entry.id === current)) {
          return current;
        }
        return nextEntries[0]!.id;
      });
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }, [query]);

  useEffect(() => {
    void loadEntries();
  }, [loadEntries]);

  useEffect(() => {
    if (!selectedId) {
      setSkillMarkdown(null);
      return;
    }
    let cancelled = false;
    setSkillLoading(true);
    void (async () => {
      try {
        const skillResult = await getKnowledgeSkill(selectedId);
        if (!cancelled) {
          setSkillMarkdown(skillResult.data.markdown);
          setStatus(null);
        }
      } catch (error) {
        if (!cancelled) {
          setStatus(getErrorMessage(error));
          setSkillMarkdown(null);
        }
      } finally {
        if (!cancelled) {
          setSkillLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const handleOpen = (entryId: string) => {
    setSelectedId(entryId);
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>知识库</CardTitle>
          <CardDescription>已发布的结构经验条目</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <input
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="搜索标题、摘要、分类…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div className="space-y-2">
            {entries.map((entry) => (
              <div
                key={entry.id}
                role="button"
                tabIndex={0}
                className={`w-full cursor-pointer rounded-lg border p-3 text-left hover:bg-muted/40 ${
                  selectedId === entry.id
                    ? "border-primary bg-muted/30"
                    : "border-border"
                }`}
                onClick={() => handleOpen(entry.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    handleOpen(entry.id);
                  }
                }}
              >
                <div className="font-medium">{entry.title}</div>
                <div className="text-xs text-muted-foreground">
                  {entry.category} · {entry.style}
                </div>
                <div className="mt-1 text-sm text-muted-foreground">{entry.summary}</div>
                {onSelect && (
                  <div className="mt-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelect(entry.id);
                      }}
                    >
                      选用此条目
                    </Button>
                  </div>
                )}
              </div>
            ))}
            {entries.length === 0 && (
              <p className="text-sm text-muted-foreground">暂无已发布知识条目。</p>
            )}
          </div>
        </CardContent>
      </Card>
      {entries.length > 0 && (
        skillLoading || !skillMarkdown ? (
          <Card>
            <CardHeader>
              <CardTitle>Skill 预览</CardTitle>
              <CardDescription>支持标题、列表、粗体与代码块渲染</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {skillLoading ? "加载 Skill 预览…" : "暂无 Skill 内容。"}
              </p>
            </CardContent>
          </Card>
        ) : (
          <KnowledgeMarkdownPreview markdown={skillMarkdown} />
        )
      )}
      {status && <p className="text-sm text-destructive lg:col-span-2">{status}</p>}
    </div>
  );
}
