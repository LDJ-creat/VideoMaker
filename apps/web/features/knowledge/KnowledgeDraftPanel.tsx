"use client";

import { useEffect, useState } from "react";

import { KnowledgeMarkdownPreview } from "@/features/knowledge/KnowledgeMarkdownPreview";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getKnowledgeDraft, promoteKnowledgeDraft } from "@/lib/apiClient";
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
  const [markdown, setMarkdown] = useState<string | null>(null);
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
        setMarkdown(result.data.skillMarkdown);
        const meta = result.data.entryMeta as Record<string, string>;
        setTitle(String(meta.title ?? ""));
        setCategory(String(meta.category ?? "通用短视频"));
        setStyle(String(meta.style ?? "标准结构"));
        setHookType(String(meta.hookType ?? ""));
      } catch {
        if (!cancelled) setMarkdown(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, sampleId]);

  if (!markdown) return null;

  const handlePromote = async () => {
    setLoading(true);
    setStatus(null);
    try {
      await promoteKnowledgeDraft(projectId, sampleId, {
        title: title || "结构经验",
        category,
        style,
        hookType: hookType || undefined,
      });
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
          <CardTitle>知识草稿</CardTitle>
          <CardDescription>
            样例分析完成后自动生成。确认内容后可 promote 到全局知识库。
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
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
            <Button type="button" disabled={loading} onClick={() => void handlePromote()}>
              加入知识库
            </Button>
            {status && <p className="text-sm text-muted-foreground">{status}</p>}
          </div>
          <KnowledgeMarkdownPreview markdown={markdown} />
        </CardContent>
      </Card>
    </div>
  );
}
