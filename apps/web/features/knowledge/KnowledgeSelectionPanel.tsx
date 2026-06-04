"use client";

import { useCallback, useEffect, useState } from "react";

import { KnowledgeMarkdownPreview, KnowledgeReasonTags } from "@/features/knowledge/KnowledgeMarkdownPreview";
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
  recommendKnowledge,
  resetKnowledgeSelection,
  updateKnowledgeSelection,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

type KnowledgeSelectionPanelProps = {
  projectId: string;
  onApplied?: () => void;
};

export function KnowledgeSelectionPanel({
  projectId,
  onApplied,
}: KnowledgeSelectionPanelProps) {
  const [selection, setSelection] = useState<ProjectKnowledgeSelection | null>(null);
  const [recommendation, setRecommendation] = useState<KnowledgeRecommendation | null>(null);
  const [primaryEntry, setPrimaryEntry] = useState<KnowledgeEntry | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const selectionResult = await getKnowledgeSelection(projectId);
      const currentSelection = selectionResult.data.selection;
      setSelection(currentSelection);

      const recommendResult = await recommendKnowledge(projectId);
      setRecommendation(recommendResult.data.recommendation);

      const primaryId =
        recommendResult.data.selection?.primaryEntryId ??
        currentSelection?.primaryEntryId;
      if (primaryId) {
        const entryResult = await getKnowledgeEntry(primaryId);
        setPrimaryEntry(entryResult.data);
      } else {
        setPrimaryEntry(null);
      }
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleSelect = async (entryId: string) => {
    setLoading(true);
    setStatus(null);
    try {
      await updateKnowledgeSelection(projectId, {
        primaryEntryId: entryId,
        applyStructure: false,
      });
      await refresh();
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const handleApplyStructure = async (entryId: string) => {
    setLoading(true);
    setStatus(null);
    try {
      await applyKnowledgeToProject(projectId, { entryId, applyStructure: true });
      await refresh();
      onApplied?.();
    } catch (error) {
      setStatus(getErrorMessage(error));
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>推荐知识</CardTitle>
        <CardDescription>
          系统会根据 Brief 自动选用最匹配的结构经验；你也可以手动切换。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && <p className="text-sm text-muted-foreground">加载推荐知识…</p>}
        {primaryEntry ? (
          <div className="space-y-2">
            <p className="text-sm">
              已{selection?.mode === "user_override" ? "手动" : "自动"}选用：
              <span className="ml-1 font-medium">{primaryEntry.title}</span>
            </p>
            <p className="text-sm text-muted-foreground">{primaryEntry.summary}</p>
            <KnowledgeReasonTags reasons={activeCandidate?.reasons ?? []} />
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="outline" onClick={() => setExpanded((v) => !v)}>
                {expanded ? "收起候选" : "查看其他推荐"}
              </Button>
              <Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => void handleReset()}>
                恢复自动选用
              </Button>
              {selection?.primaryEntryId && (
                <Button
                  type="button"
                  size="sm"
                  disabled={loading}
                  onClick={() => void handleApplyStructure(selection.primaryEntryId!)}
                >
                  应用为项目结构
                </Button>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            暂无已发布知识库条目。完成样例分析并 promote 后即可自动推荐。
          </p>
        )}

        {expanded && recommendation && (
          <div className="space-y-2">
            {recommendation.candidates.map((candidate) => (
              <div
                key={candidate.entryId}
                className="rounded-lg border border-border p-3 text-sm"
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="font-medium">{candidate.entry.title}</span>
                  <Badge variant="secondary">{(candidate.score * 100).toFixed(0)}%</Badge>
                </div>
                <p className="text-muted-foreground">{candidate.entry.summary}</p>
                <KnowledgeReasonTags reasons={candidate.reasons} />
                <div className="mt-2 flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={loading}
                    onClick={() => void handleSelect(candidate.entryId)}
                  >
                    选用
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={loading}
                    onClick={() => void handleApplyStructure(candidate.entryId)}
                  >
                    应用结构
                  </Button>
                </div>
              </div>
            ))}
          </div>
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
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const loadEntries = useCallback(async () => {
    try {
      const result = await listKnowledgeEntries({ q: query || undefined });
      setEntries(result.data.entries);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }, [query]);

  useEffect(() => {
    void loadEntries();
  }, [loadEntries]);

  const handleOpen = async (entryId: string) => {
    setSelectedId(entryId);
    try {
      const result = await getKnowledgeEntry(entryId);
      const skillResult = await getKnowledgeSkill(entryId);
      setSkillMarkdown(skillResult.data.markdown);
      setSelectedId(result.data.id);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
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
              <button
                key={entry.id}
                type="button"
                className="w-full rounded-lg border border-border p-3 text-left hover:bg-muted/40"
                onClick={() => void handleOpen(entry.id)}
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
              </button>
            ))}
            {entries.length === 0 && (
              <p className="text-sm text-muted-foreground">暂无已发布知识条目。</p>
            )}
          </div>
        </CardContent>
      </Card>
      {selectedId && skillMarkdown && (
        <KnowledgeMarkdownPreview markdown={skillMarkdown} />
      )}
      {status && <p className="text-sm text-destructive lg:col-span-2">{status}</p>}
    </div>
  );
}
