import { ProjectWorkbench } from "@/features/workbench/ProjectWorkbench";

type PageProps = {
  params: Promise<{ projectId: string }>;
};

export default async function ProjectDetailPage({ params }: PageProps) {
  const { projectId } = await params;
  return <ProjectWorkbench projectId={projectId} />;
}
