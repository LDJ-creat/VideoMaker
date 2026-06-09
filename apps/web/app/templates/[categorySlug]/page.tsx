"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { SamplePreviewDialog } from "@/components/sample-preview-dialog";
import { CategoryTemplateHero } from "@/features/knowledge-template/CategoryTemplateHero";
import {
  TemplateEntryCard,
  type TemplateEntryRole,
} from "@/features/knowledge-template/TemplateEntryCard";
import { TemplateSelectionDock } from "@/features/knowledge-template/TemplateSelectionDock";
import { TemplateSelectionSheet } from "@/features/knowledge-template/TemplateSelectionSheet";
import type { ActiveSampleSummary, KnowledgeCategoryDetail, KnowledgeCategoryEntryCard } from "@/lib/apiClient";
import {
  createProjectFromKnowledgeTemplate,
  getKnowledgeCategory,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

function defaultProjectName(category: string): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${category} · ${month}-${day}`;
}

function entryToPreviewSample(entry: KnowledgeCategoryEntryCard): ActiveSampleSummary {
  return {
    id: entry.entryId,
    status: "analyzed",
    sourceKind: "local",
    hasStructure: true,
    previewUrl: entry.previewUrl ?? undefined,
    posterUrl: entry.posterUrl ?? undefined,
    fileName: entry.title,
  };
}

export default function CategoryTemplatePage() {
  const params = useParams<{ categorySlug: string }>();
  const categorySlug = decodeURIComponent(params.categorySlug);
  const router = useRouter();

  const [detail, setDetail] = useState<KnowledgeCategoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [primaryEntryId, setPrimaryEntryId] = useState<string | null>(null);
  const [referenceEntryIds, setReferenceEntryIds] = useState<string[]>([]);
  const [projectName, setProjectName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [previewEntry, setPreviewEntry] = useState<KnowledgeCategoryEntryCard | null>(null);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const { data } = await getKnowledgeCategory(categorySlug);
      setDetail(data);
      setProjectName((current) => current || defaultProjectName(data.category));
    } catch (err) {
      setLoadError(getErrorMessage(err));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [categorySlug]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const entriesById = useMemo(() => {
    const map = new Map<string, KnowledgeCategoryEntryCard>();
    for (const entry of detail?.entries ?? []) {
      map.set(entry.entryId, entry);
    }
    return map;
  }, [detail?.entries]);

  const handleSetPrimary = useCallback((entryId: string) => {
    setPrimaryEntryId(entryId);
    setReferenceEntryIds((prev) => prev.filter((id) => id !== entryId));
    setCreateError(null);
  }, []);

  const handleToggleReference = useCallback(
    (entryId: string) => {
      if (entryId === primaryEntryId) return;
      setReferenceEntryIds((prev) => {
        if (prev.includes(entryId)) {
          return prev.filter((id) => id !== entryId);
        }
        if (prev.length >= 2) {
          return prev;
        }
        return [...prev, entryId];
      });
      setCreateError(null);
    },
    [primaryEntryId],
  );

  const handleCreate = useCallback(async () => {
    if (!primaryEntryId || !projectName.trim() || !detail) return;

    setCreating(true);
    setCreateError(null);
    try {
      const { data } = await createProjectFromKnowledgeTemplate({
        name: projectName.trim(),
        categorySlug: detail.categorySlug,
        primaryEntryId,
        referenceEntryIds,
      });
      router.push(`/projects/${data.project.id}`);
    } catch (err) {
      setCreateError(getErrorMessage(err));
      setCreating(false);
    }
  }, [detail, primaryEntryId, projectName, referenceEntryIds, router]);

  const referencesFull = referenceEntryIds.length >= 2;

  const getRole = (entryId: string): TemplateEntryRole => {
    if (entryId === primaryEntryId) return "primary";
    if (referenceEntryIds.includes(entryId)) return "reference";
    return null;
  };

  const selectionProps = {
    detail: detail!,
    entriesById,
    primaryEntryId,
    referenceEntryIds,
    projectName,
    creating,
    createError,
    onProjectNameChange: setProjectName,
    onRemovePrimary: () => setPrimaryEntryId(null),
    onRemoveReference: (entryId: string) =>
      setReferenceEntryIds((prev) => prev.filter((id) => id !== entryId)),
    onCreate: () => void handleCreate(),
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl space-y-6 pb-24">
        <div className="h-5 w-48 animate-pulse rounded bg-muted" />
        <div className="h-40 animate-pulse rounded-2xl bg-muted" />
        <div className="grid gap-4 sm:grid-cols-2">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="h-64 animate-pulse rounded-2xl bg-muted" />
          ))}
        </div>
      </div>
    );
  }

  if (loadError || !detail) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 pb-20">
        <nav className="text-sm text-muted-foreground">
          <Link href="/projects" className="hover:text-foreground">
            首页
          </Link>
          <span className="mx-2">/</span>
          <span>结构模板</span>
        </nav>
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-6 text-sm text-destructive">
          {loadError ?? "无法加载模板详情"}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 pb-28 lg:pb-20" data-testid="category-template-page">
      <nav className="text-sm text-muted-foreground" aria-label="面包屑">
        <Link href="/projects" className="hover:text-foreground">
          首页
        </Link>
        <span className="mx-2">/</span>
        <Link href="/projects" className="hover:text-foreground">
          结构模板
        </Link>
        <span className="mx-2">/</span>
        <span className="text-foreground">{detail.category}</span>
      </nav>

      <CategoryTemplateHero detail={detail} />

      <div className="lg:grid lg:grid-cols-[300px_1fr] lg:gap-8">
        <div className="hidden lg:block">
          <TemplateSelectionDock {...selectionProps} testId="template-selection-dock-desktop" />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {detail.entries.map((entry) => {
            const role = getRole(entry.entryId);
            const referenceIndex =
              role === "reference" ? referenceEntryIds.indexOf(entry.entryId) + 1 : undefined;
            return (
              <TemplateEntryCard
                key={entry.entryId}
                entry={entry}
                role={role}
                referenceIndex={referenceIndex}
                referencesFull={referencesFull}
                onSetPrimary={handleSetPrimary}
                onToggleReference={handleToggleReference}
                onPreview={setPreviewEntry}
              />
            );
          })}
        </div>
      </div>

      <div className="lg:hidden">
        <TemplateSelectionSheet {...selectionProps} />
      </div>

      <SamplePreviewDialog
        sample={previewEntry ? entryToPreviewSample(previewEntry) : null}
        open={previewEntry !== null}
        onClose={() => setPreviewEntry(null)}
      />
    </div>
  );
}
