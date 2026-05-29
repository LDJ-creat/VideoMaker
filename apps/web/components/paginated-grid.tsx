"use client";

import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

type PaginatedGridProps<T> = {
  items: T[];
  pageSize: number;
  getKey: (item: T) => string;
  renderItem: (item: T) => ReactNode;
  emptyMessage?: string;
  resetKey?: string | number;
};

export function PaginatedGrid<T>({
  items,
  pageSize,
  getKey,
  renderItem,
  emptyMessage,
  resetKey,
}: PaginatedGridProps<T>) {
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));

  useEffect(() => {
    setPage(0);
  }, [resetKey, items.length]);

  useEffect(() => {
    if (page > totalPages - 1) {
      setPage(Math.max(0, totalPages - 1));
    }
  }, [page, totalPages]);

  if (items.length === 0) {
    if (!emptyMessage) return null;
    return (
      <p className="text-xs text-muted-foreground">{emptyMessage}</p>
    );
  }

  const slice = items.slice(page * pageSize, page * pageSize + pageSize);

  return (
    <div className="flex min-h-0 flex-col gap-2">
      <div className="grid gap-3 sm:grid-cols-2">
        {slice.map((item) => (
          <div key={getKey(item)}>{renderItem(item)}</div>
        ))}
      </div>
      {items.length > pageSize && (
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page === 0}
            onClick={() => setPage((current) => current - 1)}
          >
            上一页
          </Button>
          <span>
            第 {page + 1} / {totalPages} 页 · 共 {items.length} 项
          </span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((current) => current + 1)}
          >
            下一页
          </Button>
        </div>
      )}
    </div>
  );
}
