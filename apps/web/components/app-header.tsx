import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 md:px-6">
        <Link href="/projects" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ai text-sm font-bold text-ai-foreground">
            VM
          </span>
          <div>
            <p className="text-sm font-semibold leading-none">VideoMaker</p>
            <p className="text-xs text-muted-foreground">
              可解释结构迁移工作台
            </p>
          </div>
        </Link>
        <ThemeToggle />
      </div>
    </header>
  );
}
