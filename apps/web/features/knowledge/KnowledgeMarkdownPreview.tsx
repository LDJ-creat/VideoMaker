"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type KnowledgeMarkdownPreviewProps = {
  markdown: string;
};

export function KnowledgeMarkdownPreview({ markdown }: KnowledgeMarkdownPreviewProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Skill 预览</CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/40 p-4 text-sm leading-relaxed">
          {markdown}
        </pre>
      </CardContent>
    </Card>
  );
}

export function KnowledgeReasonTags({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {reasons.map((reason) => (
        <Badge key={reason} variant="secondary">
          {reason}
        </Badge>
      ))}
    </div>
  );
}
