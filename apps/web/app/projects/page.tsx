"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { HeroSection } from "@/components/home/hero-section";
import { ProjectGrid } from "@/components/home/project-grid";
import { TemplateCategorySection } from "@/components/home/template-category-section";
import { WorkflowStrip } from "@/components/home/workflow-strip";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { fixtureProject } from "@/fixtures";
import {
  createProject,
  deleteProject,
  listProjects,
  type ProjectSummary,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

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

function clearDemoProjectFromSession(projectId: string) {
  const demo = loadDemoProjectFromSession();
  if (demo?.id === projectId) {
    sessionStorage.removeItem(DEMO_STORAGE_KEY);
  }
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
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

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
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(getErrorMessage(err));
      setCreating(false);
    }
  }, [name, router]);

  const loadDemoProject = () => {
    saveDemoProjectToSession(fixtureProject);
    setProjects((prev) => mergeProjects(prev, fixtureProject));
  };

  const focusNameInput = useCallback(() => {
    document.getElementById("hero")?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => nameInputRef.current?.focus(), 300);
  }, []);

  const handleDeleteRequest = useCallback((project: ProjectSummary) => {
    setDeleteError(null);
    setDeleteTarget(project);
  }, []);

  const handleDeleteCancel = useCallback(() => {
    if (deleting) return;
    setDeleteTarget(null);
    setDeleteError(null);
  }, [deleting]);

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;

    setDeleting(true);
    setDeleteError(null);

    const target = deleteTarget;
    const isDemoOnly = target.id === fixtureProject.id;

    try {
      if (!isDemoOnly) {
        await deleteProject(target.id);
      }
      clearDemoProjectFromSession(target.id);
      setProjects((prev) => prev.filter((project) => project.id !== target.id));
      setDeleteTarget(null);
    } catch (err) {
      if (isDemoOnly) {
        clearDemoProjectFromSession(target.id);
        setProjects((prev) => prev.filter((project) => project.id !== target.id));
        setDeleteTarget(null);
      } else {
        setDeleteError(getErrorMessage(err));
      }
    } finally {
      setDeleting(false);
    }
  }, [deleteTarget]);

  return (
    <div className="mx-auto max-w-6xl space-y-12 pb-20">
      <HeroSection
        name={name}
        creating={creating}
        error={error}
        onNameChange={setName}
        onCreate={() => void handleCreate()}
        onLoadDemo={loadDemoProject}
        inputRef={nameInputRef}
      />

      <WorkflowStrip />

      <TemplateCategorySection />

      <ProjectGrid
        projects={projects}
        loading={loading}
        onNewProjectClick={focusNameInput}
        onDeleteProject={handleDeleteRequest}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        title="确认删除项目？"
        description={
          deleteTarget
            ? `将永久删除「${deleteTarget.name}」及其所有样例、素材、生成结果与分析产物，此操作无法撤销。`
            : ""
        }
        confirmLabel="删除项目"
        cancelLabel="保留"
        destructive
        loading={deleting}
        onConfirm={() => void handleDeleteConfirm()}
        onCancel={handleDeleteCancel}
      />

      {deleteError ? (
        <p className="text-center text-sm text-destructive" role="alert">
          {deleteError}
        </p>
      ) : null}
    </div>
  );
}
