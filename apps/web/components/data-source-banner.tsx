"use client";

import { useEffect, useState } from "react";

import {
  getLastDataSource,
  subscribeDataSource,
} from "@/lib/data-source-store";

export function DataSourceBanner() {
  const [source, setSource] = useState(getLastDataSource());

  useEffect(() => subscribeDataSource(setSource), []);

  if (source !== "fixture") {
    return null;
  }

  return (
    <div
      role="status"
      className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-800 dark:text-amber-200"
    >
      当前展示的是演示数据（后端不可达或已启用 VIDEOMAKER_USE_FIXTURE_FALLBACK）。
    </div>
  );
}
