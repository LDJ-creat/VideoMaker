"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

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
import { getApiBaseUrl } from "@/lib/config";
import { fixtureProject } from "@/fixtures";

type ProjectRow = {
  id: string;
  name: string;
  createdAt: string;
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectRow[]>([fixtureProject]);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  const handleCreate = useCallback(async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      const project = await createProject(getApiBaseUrl(), name.trim());
      setProjects((prev) => [project, ...prev]);
      setName("");
    } finally {
      setCreating(false);
    }
  }, [name]);

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
        </CardContent>
      </Card>

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
                  创建于 {new Date(project.createdAt).toLocaleString("zh-CN")}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
