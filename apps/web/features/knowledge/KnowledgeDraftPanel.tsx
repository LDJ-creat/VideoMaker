"use client";

import { useEffect, useState } from "react";

import { CheckCircle2 } from "lucide-react";

import { KnowledgeMarkdownPreview } from "@/features/knowledge/KnowledgeMarkdownPreview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getKnowledgeDraft,
  promoteKnowledgeDraft,
  type KnowledgeDraftResponse,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

type KnowledgeDraftPanelProps = {
  projectId: string;
  sampleId: string;
  onPromoted?: () => void;
};

export function KnowledgeDraftPanel({
  projectId,
  sampleId,
  onPromoted,
}: KnowledgeDraftPanelProps) {
  const [draft, setDraft] = useState<KnowledgeDraftResponse | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("通用短视频");
  const [style, setStyle] = useState("标准结构");
  const [hookType, setHookType] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const result = await getKnowledgeDraft(projectId, sampleId);
        if (cancelled) return;
        setDraft(result.data);
        const meta = result.data.entryMeta as Record<string, string>;
        setTitle(String(meta.title ?? ""));
        setCategory(String(meta.category ?? "通用短视频"));
        setStyle(String(meta.style ?? "标准结构"));
        setHookType(String(meta.hookType ?? ""));
      } catch {
        if (!cancelled) setDraft(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, sampleId]);

  if (!draft?.skillMarkdown) return null;

  const publishedEntry = draft.publishedEntry ?? null;
  const isPublished = Boolean(publishedEntry?.id);

  const handlePromote = async () => {
    setLoading(true);
    setStatus(null);
    try {
      const result = await promoteKnowledgeDraft(projectId, sampleId, {
        title: title || "结构经验",
        category,
        style,
        hookType: hookType || undefined,
      });
      setDraft((current) =>
        current
          ? {
              ...current,
              publishedEntry: {
                id: result.data.entry.id,
                title: result.data.entry.title,
                category: result.data.entry.category,
                style: result.data.entry.style,
                updatedAt: result.data.entry.updatedAt,
              },
            }
          : current,
      );
      setStatus("已加入全局知识库。");
      onPromoted?.();
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <CardTitle>知识草稿</CardTitle>
              <CardDescription>
                样例分析完成后自动生成。确认内容后可加入全局知识库供其他项目复用。
              </CardDescription>
            </div>
            {isPublished ? (
              <Badge variant="default" data-testid="knowledge-draft-published-badge">
                <CheckCircle2 className="mr-1 h-3 w-3" />
                已加入知识库
              </Badge>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
            {isPublished ? (
              <div
                className="space-y-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm"
                data-testid="knowledge-draft-published-summary"
              >
                <p className="font-medium text-foreground">
                  {publishedEntry?.title ?? "结构经验"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {publishedEntry?.category ?? category}
                  {publishedEntry?.style ? ` · ${publishedEntry.style}` : ""}
                </p>
                <p className="font-mono text-[10px] text-muted-foreground">
                  条目 ID：{publishedEntry?.id}
                </p>
                <p className="text-xs text-muted-foreground">
                  该样例已入库，无需重复提交。可在「知识库」标签页查看或绑定到生成任务。
                </p>
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="knowledge-title">标题</Label>
                  <Input
                    id="knowledge-title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="knowledge-category">分类</Label>
                  <Input
                    id="knowledge-category"
                    value={category}
                    onChange={(event) => setCategory(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="knowledge-style">风格</Label>
                  <Input
                    id="knowledge-style"
                    value={style}
                    onChange={(event) => setStyle(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="knowledge-hook">Hook 类型</Label>
                  <Input
                    id="knowledge-hook"
                    value={hookType}
                    placeholder="pain_point / result / suspense"
                    onChange={(event) => setHookType(event.target.value)}
                  />
                </div>
                <Button
                  type="button"
                  disabled={loading}
                  onClick={() => void handlePromote()}
                  data-testid="knowledge-draft-promote-button"
                >
                  加入知识库
                </Button>
              </>
            )}
            {status && !isPublished ? (
              <p className="text-sm text-muted-foreground">{status}</p>
            ) : null}
          </div>
          <KnowledgeMarkdownPreview markdown={draft.skillMarkdown} />
        </CardContent>
      </Card>
    </div>
  );
}
