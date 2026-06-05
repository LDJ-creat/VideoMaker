import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";
import { ArrowRight, Trash2, VideoIcon } from "lucide-react";
import Link from "next/link";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { ProjectSummary } from "@/lib/apiClient";
import { getProjectCardTheme } from "@/lib/projectCardTheme";
import { cn } from "@/lib/utils";

type ProjectCardProps = {
  project: ProjectSummary;
  onDelete: (project: ProjectSummary) => void;
};

export function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const theme = getProjectCardTheme(project.name);

  return (
    <div className="group relative h-full">
      <Link
        href={`/projects/${project.id}`}
        className="block h-full cursor-pointer"
      >
        <Card className="flex h-full flex-col overflow-hidden border-border bg-card shadow-sm transition-colors duration-200 hover:border-primary/30 hover:shadow-md">
          <div
            className={cn(
              "relative aspect-video w-full shrink-0 overflow-hidden border-b border-border/50 bg-gradient-to-br",
              theme.gradient,
            )}
          >
            <div
              className="pointer-events-none absolute inset-y-3 left-0 w-3 bg-[repeating-linear-gradient(180deg,transparent_0,transparent_6px,currentColor_6px,currentColor_10px)] opacity-[0.07]"
              aria-hidden="true"
            />
            <div
              className="pointer-events-none absolute inset-y-3 right-0 w-3 bg-[repeating-linear-gradient(180deg,transparent_0,transparent_6px,currentColor_6px,currentColor_10px)] opacity-[0.07]"
              aria-hidden="true"
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <VideoIcon
                className={cn(
                  "h-10 w-10 transition-transform duration-300 group-hover:scale-105",
                  theme.iconColor,
                )}
              />
            </div>
          </div>

          <div className="flex flex-1 flex-col">
            <CardHeader className="p-4 pb-2">
              <CardTitle className="line-clamp-1 font-serif text-base font-semibold leading-tight">
                {project.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="mt-auto p-4 pt-1">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(project.createdAt), {
                    addSuffix: true,
                    locale: zhCN,
                  })}
                </span>
                <span className="inline-flex items-center gap-1 text-xs font-medium text-primary opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                  进入工作台
                  <ArrowRight className="h-3.5 w-3.5" />
                </span>
              </div>
            </CardContent>
          </div>
        </Card>
      </Link>

      <button
        type="button"
        aria-label={`删除项目 ${project.name}`}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onDelete(project);
        }}
        className={cn(
          "absolute right-3 top-3 z-10 flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg",
          "border border-border/60 bg-background/90 text-muted-foreground shadow-sm backdrop-blur-sm",
          "opacity-0 transition-all duration-200 hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive",
          "group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}
