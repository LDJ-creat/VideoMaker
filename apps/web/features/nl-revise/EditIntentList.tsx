"use client";

import type { EditIntentItem } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

import {
  EDIT_INTENT_OPERATION_LABELS,
  EDIT_INTENT_TARGET_LABELS,
} from "./intentLabels";

type EditIntentListProps = {
  intents: EditIntentItem[];
  className?: string;
};

export function EditIntentList({ intents, className }: EditIntentListProps) {
  if (intents.length === 0) {
    return null;
  }

  return (
    <Card className={cn("border-ai/20", className)} data-testid="edit-intent-list">
      <CardHeader>
        <CardTitle>改片意图</CardTitle>
        <CardDescription>AI 已从自然语言指令解析出以下结构化改片步骤</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {intents.map((intent, index) => (
          <div
            key={`${intent.target}-${intent.operation}-${index}`}
            className="rounded-lg border border-border p-3"
            data-testid={`edit-intent-item-${index}`}
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge variant="ai">
                {EDIT_INTENT_OPERATION_LABELS[intent.operation] ??
                  intent.operation}
              </Badge>
              <Badge variant="outline">
                {EDIT_INTENT_TARGET_LABELS[intent.target] ?? intent.target}
              </Badge>
            </div>
            <p className="text-sm">{intent.rationale}</p>
            {Object.keys(intent.params).length > 0 && (
              <p className="mt-2 font-mono text-xs text-muted-foreground">
                参数 {JSON.stringify(intent.params)}
              </p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
