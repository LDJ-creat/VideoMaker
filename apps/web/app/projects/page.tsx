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
import { createProject } from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import { fixtureProject } from "@/fixtures";

const STORAGE_KEY = "videomaker:projects";

type ProjectRow = {
  id: string;
  name: string;
  createdAt: string;
};

function loadProjects(): ProjectRow[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ProjectRow[];
  } catch {
    return [];
  }
}

function saveProjects(projects: ProjectRow[]) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setProjects(loadProjects());
  }, []);

  const handleCreate = useCallback(async () => {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const { data: project } = await createProject(name.trim());
      setProjects((prev) => {
        const next = [project, ...prev];
        saveProjects(next);
        return next;
      });
      setName("");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setCreating(false);
    }
  }, [name]);

  const loadDemoProject = () => {
    setProjects((prev) => {
      if (prev.some((p) => p.id === fixtureProject.id)) return prev;
      const next = [fixtureProject, ...prev];
      saveProjects(next);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">项目</h1>
        <p className="text-muted-foreground">
          创建项目后，上传样例视频、素材与 Brief，开始结构迁移。
        </p>
      </div>

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

      {projects.length === 0 ? (
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
