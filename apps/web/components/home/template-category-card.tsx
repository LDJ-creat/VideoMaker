import { Film } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { KnowledgeCategorySummary } from "@/lib/apiClient";

type TemplateCategoryCardProps = {
  category: KnowledgeCategorySummary;
};

function formatCategoryUpdatedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString("zh-CN", {
    month: "numeric",
    day: "numeric",
  });
}

export function TemplateCategoryCard({ category }: TemplateCategoryCardProps) {
  const href = `/templates/${encodeURIComponent(category.categorySlug)}`;
  const updatedLabel = formatCategoryUpdatedAt(category.updatedAt);
  const metaLine = updatedLabel
    ? `${category.entryCount} 个参考样例 · ${updatedLabel}`
    : `${category.entryCount} 个参考样例`;

  return (
    <Link
      href={href}
      className="block h-full cursor-pointer"
      data-testid="template-category-card"
      aria-label={`${category.category}，${category.entryCount} 个参考样例`}
    >
      <Card className="flex h-full flex-col overflow-hidden border-border bg-card shadow-sm transition-colors duration-200 hover:border-primary/30 hover:shadow-md">
        <div className="relative aspect-video w-full shrink-0 overflow-hidden border-b border-border/50 bg-muted">
          {category.coverUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={category.coverUrl}
              alt=""
              loading="lazy"
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-br from-studio-cream to-studio-wheat">
              <Film className="h-8 w-8 text-primary/50" aria-hidden />
            </div>
          )}
          <div
            className="pointer-events-none absolute inset-y-3 left-0 w-3 bg-[repeating-linear-gradient(180deg,transparent_0,transparent_6px,currentColor_6px,currentColor_10px)] opacity-[0.07]"
            aria-hidden
          />
          <div
            className="pointer-events-none absolute inset-y-3 right-0 w-3 bg-[repeating-linear-gradient(180deg,transparent_0,transparent_6px,currentColor_6px,currentColor_10px)] opacity-[0.07]"
            aria-hidden
          />
          <Badge variant="ai" className="absolute left-3 top-3 bg-background/90">
            结构模板
          </Badge>
        </div>
        <CardHeader className="space-y-1 p-4 pb-2">
          <h3 className="line-clamp-1 font-serif text-base font-semibold leading-tight">
            {category.category}
          </h3>
          <p className="text-xs text-muted-foreground">{metaLine}</p>
        </CardHeader>
        <CardContent className="mt-auto space-y-2 p-4 pt-0">
          {category.slotPatterns[0] ? (
            <p className="truncate font-mono text-xs text-muted-foreground">
              {category.slotPatterns[0]}
            </p>
          ) : null}
          <p className="line-clamp-2 text-sm text-muted-foreground">{category.summary}</p>
        </CardContent>
      </Card>
    </Link>
  );
}

export function TemplateCategoryCardSkeleton() {
  return (
    <Card className="overflow-hidden border-border bg-card">
      <div className="aspect-video w-full animate-pulse bg-muted" />
      <div className="space-y-2 p-4">
        <div className="h-5 w-2/3 animate-pulse rounded bg-muted" />
        <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
        <div className="h-4 w-full animate-pulse rounded bg-muted" />
      </div>
    </Card>
  );
}
