"use client";

import type { ArtifactRef, TaskStage } from "@videomaker/contracts";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { isMaterialStage } from "@/features/tasks/stageLabels";
import { artifactDisplayUrl } from "@/lib/artifactUrl";

type TaskArtifactPreviewProps = {
  projectId: string;
  artifactRefs?: ArtifactRef[];
  stage?: TaskStage;
};

function dedupeArtifacts(refs: ArtifactRef[]): ArtifactRef[] {
  const seen = new Set<string>();
  const result: ArtifactRef[] = [];
  for (const ref of refs) {
    if (seen.has(ref.id)) continue;
    seen.add(ref.id);
    result.push(ref);
  }
  return result;
}

function JsonSnippet({ uri }: { uri: string }) {
  const [content, setContent] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open || content !== null || loadError) return;
    let cancelled = false;
    void fetch(uri)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.text();
      })
      .then((text) => {
        if (!cancelled) setContent(text.slice(0, 2000));
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [content, loadError, open, uri]);

  return (
    <div className="space-y-1">
      <button
        type="button"
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {open ? "收起" : "展开"} JSON
      </button>
      {open && (
        <pre className="max-h-32 overflow-auto rounded bg-muted/50 p-2 font-mono text-xs">
          {loadError ? "无法加载预览" : (content ?? "加载中…")}
        </pre>
      )}
    </div>
  );
}

function ArtifactItem({
  projectId,
  ref,
}: {
  projectId: string;
  ref: ArtifactRef;
}) {
  const displayUrl = artifactDisplayUrl(projectId, ref);

  return (
    <li className="rounded-md border border-border/60 bg-muted/20 p-2">
      <div className="mb-1 flex items-center gap-2">
        <Badge variant="outline" className="text-xs">
          {ref.type}
        </Badge>
        <span className="truncate font-mono text-xs text-muted-foreground">
          {ref.id}
        </span>
      </div>

      {ref.type === "image" && displayUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={displayUrl}
          alt={ref.id}
          className="max-h-32 rounded border object-contain"
        />
      )}

      {ref.type === "video" && displayUrl && (
        <video
          src={displayUrl}
          controls
          className="max-h-32 w-full rounded border"
          preload="metadata"
        />
      )}

      {ref.type === "audio" && displayUrl && (
        <audio src={displayUrl} controls className="w-full" preload="metadata" />
      )}

      {(ref.type === "json" || ref.type === "text") && displayUrl && (
        <JsonSnippet uri={displayUrl} />
      )}

      {(ref.type === "html" || ref.type === "render") && displayUrl && (
        <a
          href={displayUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          打开预览
        </a>
      )}

      {!displayUrl && (
        <p className="truncate font-mono text-xs text-muted-foreground">{ref.uri}</p>
      )}
    </li>
  );
}

export function TaskArtifactPreview({
  projectId,
  artifactRefs,
  stage,
}: TaskArtifactPreviewProps) {
  const artifacts = useMemo(
    () => dedupeArtifacts(artifactRefs ?? []),
    [artifactRefs],
  );
  const [expanded, setExpanded] = useState(
    stage ? isMaterialStage(stage) : false,
  );

  useEffect(() => {
    if (stage && isMaterialStage(stage)) {
      setExpanded(true);
    }
  }, [stage]);

  if (artifacts.length === 0) return null;

  return (
    <div className="space-y-2" data-testid="task-artifact-preview">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-8 px-2"
        onClick={() => setExpanded((value) => !value)}
      >
        {expanded ? (
          <ChevronDown className="mr-1 h-4 w-4" />
        ) : (
          <ChevronRight className="mr-1 h-4 w-4" />
        )}
        阶段产物
        <Badge variant="secondary" className="ml-2">
          {artifacts.length}
        </Badge>
      </Button>

      {expanded && (
        <ul className="grid gap-2 sm:grid-cols-2">
          {artifacts.map((ref) => (
            <ArtifactItem key={ref.id} projectId={projectId} ref={ref} />
          ))}
        </ul>
      )}
    </div>
  );
}
