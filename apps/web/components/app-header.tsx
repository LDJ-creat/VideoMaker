import Link from "next/link";
import { Settings } from "lucide-react";

import { VideoMakerLogo } from "@/components/brand/video-maker-logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

export function AppHeader() {
  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-50 px-4 pt-4 md:px-6">
      <div className="pointer-events-auto mx-auto flex h-14 max-w-7xl items-center justify-between rounded-2xl border border-border/60 bg-background/85 px-4 shadow-sm backdrop-blur-md md:px-6">
        <Link
          href="/projects"
          className="flex items-center gap-3 transition-opacity hover:opacity-80"
        >
          <VideoMakerLogo size="sm" />
          <div>
            <p className="font-serif text-sm font-semibold leading-none tracking-tight">
              VideoMaker
            </p>
            <p className="text-xs text-muted-foreground">可解释结构迁移工作台</p>
          </div>
        </Link>
        <div className="flex items-center gap-2">
          <Link href="/settings" tabIndex={-1}>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 text-muted-foreground hover:bg-orange-50 hover:text-foreground dark:hover:bg-stone-800"
            >
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
