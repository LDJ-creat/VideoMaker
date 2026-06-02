"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ModelGatewayStatusPanel } from "@/features/settings/ModelGatewayStatusPanel";
import { createProject, listProjects, type ProjectSummary } from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import { fixtureProject } from "@/fixtures";

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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">项目</h1>
        <p className="text-muted-foreground">
          创建项目后，上传样例视频、素材与 Brief，开始结构迁移。
        </p>
      </div>

      <ModelGatewayStatusPanel />

      <Card>
        <CardHeader>
          <CardTitle>新建项目</CardTitle>
          <CardDescription>每个项目对应一次结构迁移任务链</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Input
            placeholder="项目名称，例如：夏季防晒喷雾"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void handleCreate()}
          />
          <Button
            type="button"
            disabled={creating || !name.trim()}
            onClick={() => void handleCreate()}
          >
            {creating ? "创建中…" : "创建项目"}
          </Button>
          <Button type="button" variant="outline" onClick={loadDemoProject}>
            加载演示项目
          </Button>
        </CardContent>
        {error && (
          <CardContent className="pt-0">
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          </CardContent>
        )}
      </Card>

      {loading ? (
        <p className="text-sm text-muted-foreground">正在加载项目…</p>
      ) : projects.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          暂无项目，请创建新项目或加载演示项目。
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Link key={project.id} href={`/projects/${project.id}`}>
              <Card className="h-full cursor-pointer transition-shadow hover:shadow-md">
                <CardHeader>
                  <CardTitle className="line-clamp-1">{project.name}</CardTitle>
                  <CardDescription className="font-mono text-xs">
                    {project.id}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground">
                    创建于{" "}
                    {new Date(project.createdAt).toLocaleString("zh-CN")}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
