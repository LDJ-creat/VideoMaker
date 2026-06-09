import { Badge } from "@/components/ui/badge";
import type { KnowledgeCategoryDetail } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

type CategoryTemplateHeroProps = {
  detail: KnowledgeCategoryDetail;
};

export function CategoryTemplateHero({ detail }: CategoryTemplateHeroProps) {
  const mosaic = detail.entries
    .filter((entry) => entry.posterUrl)
    .slice(0, 3);

  return (
    <section className="rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
      <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-start">
        <div className="space-y-4">
          <Badge variant="outline" className="border-primary/40 text-primary">
            结构模板 · {detail.entries.length} 个样例参考
          </Badge>
          <h1 className="font-serif text-3xl font-semibold tracking-tight">
            {detail.category}
          </h1>
          {detail.entries[0]?.summary ? (
            <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground line-clamp-3">
              {detail.entries[0].summary}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {detail.entries[0]?.slotPattern ? (
              <Badge variant="ai">{detail.entries[0].slotPattern}</Badge>
            ) : null}
            {detail.entries[0]?.tempo ? (
              <Badge variant="secondary">{detail.entries[0].tempo}</Badge>
            ) : null}
            {detail.entries[0]?.durationBucket ? (
              <Badge variant="outline">{detail.entries[0].durationBucket}</Badge>
            ) : null}
          </div>
        </div>
        {mosaic.length > 0 ? (
          <div className="hidden items-end gap-2 lg:flex">
            {mosaic.map((entry, index) => (
              <div
                key={entry.entryId}
                className={cn(
                  "h-24 w-16 overflow-hidden rounded-lg border border-border/80 shadow-sm",
                  index === 0 && "-rotate-2",
                  index === 2 && "rotate-2",
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={entry.posterUrl!}
                  alt=""
                  className="h-full w-full object-cover"
                />
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
