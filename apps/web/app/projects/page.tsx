"use client";

import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";
import { Sparkles, Video, ArrowRight, VideoIcon, AlertCircle } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createProject, listProjects, type ProjectSummary } from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import { fixtureProject } from "@/fixtures";
import { Badge } from "@/components/ui/badge";

const DEMO_STORAGE_KEY = "videomaker:demo-project";

function loadDemoProjectFromSession(): ProjectSummary | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(DEMO_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as ProjectSummary;
  } catch {
    return null;
  }
}

function saveDemoProjectToSession(project: ProjectSummary) {
  sessionStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(project));
}

function mergeProjects(
  apiProjects: ProjectSummary[],
  demoProject: ProjectSummary | null,
): ProjectSummary[] {
  const merged = [...apiProjects];
  if (demoProject && !merged.some((project) => project.id === demoProject.id)) {
    merged.unshift(demoProject);
  }
  return merged;
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const { data } = await listProjects();
        if (cancelled) return;
        setProjects(mergeProjects(data.projects, loadDemoProjectFromSession()));
      } catch (err) {
        if (!cancelled) {
          setError(getErrorMessage(err));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleCreate = useCallback(async () => {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const { data: project } = await createProject(name.trim());
      setProjects((prev) => mergeProjects([project, ...prev], loadDemoProjectFromSession()));
      setName("");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setCreating(false);
    }
  }, [name]);

  const loadDemoProject = () => {
    saveDemoProjectToSession(fixtureProject);
    setProjects((prev) => mergeProjects(prev, fixtureProject));
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8 pb-20 mt-4 md:mt-8 px-4 sm:px-6 lg:px-8">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-violet-600 via-indigo-600 to-blue-700 px-6 py-16 text-center text-white shadow-2xl dark:from-violet-900 dark:via-indigo-900 dark:to-blue-950 sm:py-24">
        {/* Abstract Background Elements */}
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-10 mix-blend-overlay"></div>
        <div className="absolute -top-24 -left-24 h-96 w-96 rounded-full bg-white/10 blur-3xl"></div>
        <div className="absolute right-0 bottom-0 h-64 w-64 rounded-full bg-blue-500/20 blur-3xl"></div>

        <div className="relative z-10 mx-auto max-w-3xl space-y-6">
          <Badge className="bg-white/20 text-white hover:bg-white/30 backdrop-blur-md mb-2 border-0">VideoMaker Beta</Badge>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl text-balance drop-shadow-sm">
             让爆款视频的结构 <br className="hidden sm:block" /> 为您所用
          </h1>
          <p className="mx-auto max-w-xl text-lg text-indigo-100 sm:text-xl drop-shadow-sm">
            上传高转化样例视频，一键提取镜头结构与爆款脚本，结合您的素材，自动化生成专属视频创意。
          </p>

          <div className="mx-auto mt-8 flex max-w-lg flex-col gap-3 sm:flex-row items-center rounded-2xl sm:rounded-full bg-white/10 p-2 backdrop-blur-md focus-within:bg-white/20 transition-all border border-white/20 shadow-inner">
            <Input
              placeholder="为新项目命名，如：夏季防晒喷雾"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleCreate()}
              className="h-12 w-full border-0 bg-transparent text-white placeholder:text-white/60 focus-visible:ring-0 focus-visible:ring-offset-0 sm:px-4 text-base"
            />
            <Button
              size="lg"
              disabled={creating || !name.trim()}
              onClick={() => void handleCreate()}
              className="w-full sm:w-auto h-12 rounded-xl sm:rounded-full bg-white text-indigo-700 hover:bg-indigo-50 font-semibold shadow-lg transition-transform active:scale-95 px-8"
            >
              <Sparkles className="mr-2 h-4 w-4" />
              {creating ? "创建中…" : "开始创建"}
            </Button>
          </div>
          
          {error && (
            <p className="mx-auto mt-4 max-w-md text-sm text-red-100 bg-red-900/50 inline-flex items-center gap-2 px-4 py-2 rounded-full border border-red-500/30">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span className="truncate">{error}</span>
            </p>
          )}

          <div className="mt-8 flex items-center justify-center gap-4 text-sm text-indigo-200">
            <span>还没想好怎么做？</span>
            <button onClick={loadDemoProject} className="flex items-center gap-1 font-medium text-white hover:text-indigo-100 hover:underline underline-offset-4 transition-colors">
              加载演示项目 <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Projects List */}
      <div className="space-y-6 pt-4">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
             我的创意库 
             <span className="text-sm font-normal text-muted-foreground bg-secondary px-2 py-0.5 rounded-full">{projects.length} </span>
          </h2>
        </div>

        {loading ? (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {[1, 2, 3].map(i => (
              <Card key={i} className="animate-pulse overflow-hidden bg-zinc-50 dark:bg-zinc-900/50">
                <div className="aspect-video w-full bg-zinc-200 dark:bg-zinc-800" />
                <CardHeader className="p-5 pb-4"><div className="h-5 w-3/4 rounded bg-zinc-200 dark:bg-zinc-800" /></CardHeader>
                <CardContent className="p-5 pt-0"><div className="h-4 w-1/2 rounded bg-zinc-200 dark:bg-zinc-800" /></CardContent>
              </Card>
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed py-24 text-center bg-zinc-50/50 dark:bg-zinc-950/50">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 mb-6">
              <Video className="h-10 w-10" />
            </div>
            <h3 className="text-xl font-semibold text-foreground">暂无视频项目</h3>
            <p className="mt-2 text-sm text-muted-foreground max-w-sm">
              您还没有创建任何项目，在上方输入名称开始一段不可思议的视频生成之旅吧。
            </p>
          </div>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {projects.map((project) => (
              <Link key={project.id} href={`/projects/${project.id}`} className="group relative block h-full">
                <Card className="flex h-full flex-col overflow-hidden border-zinc-200 bg-white shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-indigo-500/10 hover:border-indigo-300 dark:border-white/10 dark:bg-zinc-950 dark:hover:border-indigo-500/50">
                  {/* Thumbnail Area */}
                  <div className="relative flex-shrink-0 aspect-video w-full overflow-hidden bg-zinc-100 dark:bg-zinc-900 border-b border-border/50">
                    <div className="absolute inset-0 bg-gradient-to-tr from-violet-500/5 to-indigo-500/10 transition-opacity group-hover:opacity-100 opacity-0" />
                    <div className="absolute inset-0 flex items-center justify-center transition-transform duration-500 group-hover:scale-110">
                      <VideoIcon className="h-10 w-10 text-indigo-500/20 dark:text-indigo-400/20" />
                    </div>
                  </div>
                  
                  <div className="flex flex-col flex-1">
                    <CardHeader className="p-4 pb-2">
                      <CardTitle className="line-clamp-1 text-base font-semibold leading-tight select-none">
                        {project.name}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-1 mt-auto">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">
                          {formatDistanceToNow(new Date(project.createdAt), { addSuffix: true, locale: zhCN })}
                        </span>
                        <Badge variant="secondary" className="bg-indigo-50 hover:bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400 font-normal border-0 text-[10px] px-2 py-0 h-5">
                          进入工作台
                        </Badge>
                      </div>
                    </CardContent>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}