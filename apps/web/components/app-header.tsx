import Link from "next/link";
import { Settings } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 md:px-6">
        <Link href="/projects" className="flex items-center gap-2 transition-opacity hover:opacity-80">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white shadow-sm dark:bg-indigo-500">
            VM
          </span>
          <div>
            <p className="text-sm font-semibold leading-none tracking-tight">VideoMaker</p>
            <p className="text-xs text-muted-foreground">
              可解释结构迁移工作台
            </p>
          </div>
        </Link>
        <div className="flex items-center gap-2">
          <Link href="/settings" tabIndex={-1}>
            <Button variant="ghost" size="icon" className="h-9 w-9 text-muted-foreground hover:text-foreground">
              <Settings className="h-5 w-5" />
              <span className="sr-only">设置</span>
            </Button>
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
