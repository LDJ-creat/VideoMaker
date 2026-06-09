"use client";

import { useCallback, useEffect, useState } from "react";

import {
  TemplateCategoryCard,
  TemplateCategoryCardSkeleton,
} from "@/components/home/template-category-card";
import { Button } from "@/components/ui/button";
import { listKnowledgeCategories, type KnowledgeCategorySummary } from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

export function TemplateCategorySection() {
  const [categories, setCategories] = useState<KnowledgeCategorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await listKnowledgeCategories();
      setCategories(data.categories);
    } catch (err) {
      setError(getErrorMessage(err));
      setCategories([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!loading && categories.length === 0 && !error) {
    return null;
  }

  return (
    <section className="space-y-6" data-testid="template-category-section">
      <div className="space-y-1">
        <h2 className="flex items-center gap-2 font-serif text-2xl font-semibold tracking-tight text-foreground">
          结构模板库
          {!loading ? (
            <span className="rounded-full bg-secondary px-2 py-0.5 font-sans text-sm font-normal text-muted-foreground">
              {categories.length}
            </span>
          ) : null}
        </h2>
        <p className="text-sm leading-relaxed text-muted-foreground">
          按题材浏览已沉淀的爆款结构，选一个模板快速开项目。
        </p>
      </div>

      {error ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <span>{error}</span>
          <Button type="button" size="sm" variant="outline" onClick={() => void load()}>
            重试
          </Button>
        </div>
      ) : null}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((item) => (
            <TemplateCategoryCardSkeleton key={item} />
          ))}
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2 snap-x snap-mandatory sm:grid sm:grid-cols-2 sm:overflow-visible sm:pb-0 lg:grid-cols-3">
          {categories.slice(0, 6).map((category) => (
            <div key={category.categorySlug} className="min-w-[280px] snap-start sm:min-w-0">
              <TemplateCategoryCard category={category} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
