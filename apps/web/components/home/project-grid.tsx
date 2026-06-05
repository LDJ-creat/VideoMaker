import { Plus, Video } from "lucide-react";

import { ProjectCard } from "@/components/home/project-card";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import type { ProjectSummary } from "@/lib/apiClient";

type ProjectGridProps = {
  projects: ProjectSummary[];
  loading: boolean;
  onNewProjectClick: () => void;
  onDeleteProject: (project: ProjectSummary) => void;
};

function ProjectCardSkeleton() {
  return (
    <Card className="overflow-hidden border-border bg-card">
      <div className="aspect-video w-full animate-pulse bg-muted" />
      <CardHeader className="p-4 pb-2">
        <div className="h-5 w-3/4 animate-pulse rounded bg-muted" />
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
      </CardContent>
    </Card>
  );
}

function NewProjectCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-full min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-border bg-muted/20 p-6 text-center transition-colors duration-200 hover:border-primary/40 hover:bg-secondary/40"
    >
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-border bg-card">
        <Plus className="h-6 w-6 text-primary" />
      </div>
      <p className="font-serif text-sm font-semibold text-foreground">新建项目</p>
      <p className="mt-1 text-xs text-muted-foreground">从上方输入名称开始创作</p>
    </button>
  );
}

export function ProjectGrid({
  projects,
  loading,
  onNewProjectClick,
  onDeleteProject,
}: ProjectGridProps) {
  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="flex items-center gap-2 font-serif text-2xl font-semibold tracking-tight text-foreground">
          我的创意库
          <span className="rounded-full bg-secondary px-2 py-0.5 font-sans text-sm font-normal text-muted-foreground">
            {projects.length}
          </span>
        </h2>
      </div>

      {loading ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[1, 2, 3].map((i) => (
            <ProjectCardSkeleton key={i} />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-border bg-muted/20 py-24 text-center">
          <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-secondary text-primary">
            <Video className="h-10 w-10" />
          </div>
          <h3 className="font-serif text-xl font-semibold text-foreground">暂无视频项目</h3>
          <p className="mt-2 max-w-sm text-sm text-muted-foreground">
            您还没有创建任何项目，在上方输入名称开始一段视频结构迁移之旅吧。
          </p>
          <Button
            type="button"
            variant="outline"
            className="mt-6 cursor-pointer"
            onClick={onNewProjectClick}
          >
            前往创建
          </Button>
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onDelete={onDeleteProject}
            />
          ))}
          <NewProjectCard onClick={onNewProjectClick} />
        </div>
      )}
    </section>
  );
}
