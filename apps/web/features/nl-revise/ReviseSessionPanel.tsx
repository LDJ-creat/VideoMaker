"use client";

import type { ReviseSession } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

type ReviseSessionPanelProps = {
  session: ReviseSession | null;
  className?: string;
};

export function ReviseSessionPanel({ session, className }: ReviseSessionPanelProps) {
  if (!session || session.turns.length === 0) {
    return null;
  }

  return (
    <Card className={cn(className)} data-testid="revise-session-panel">
      <CardHeader>
        <CardTitle>改片对话</CardTitle>
        <CardDescription>
          {session.conversationSummary ?? "本轮改片历史"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {session.turns.map((turn) => (
          <div
            key={turn.turnId}
            className="rounded-lg border border-border p-3 text-sm"
            data-testid={`revise-session-turn-${turn.turnId}`}
          >
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Badge variant="outline">{turn.status}</Badge>
              {turn.costTier && <Badge variant="secondary">{turn.costTier}</Badge>}
            </div>
            <p className="font-medium">{turn.instruction}</p>
            {turn.planSummary && (
              <p className="mt-1 text-muted-foreground">{turn.planSummary}</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
