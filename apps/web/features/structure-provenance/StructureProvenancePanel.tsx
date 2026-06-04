"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { StructureProvenanceSummary } from "@/lib/apiClient";

type StructureProvenancePanelProps = {
  provenance: StructureProvenanceSummary;
};

export function StructureProvenancePanel({
  provenance,
}: StructureProvenancePanelProps) {
  const [expanded, setExpanded] = useState(false);
  const preview = provenance.slotAttribution.slice(0, 6);

  return (
    <Card>
      <CardHeader>
        <CardTitle>结构合成溯源</CardTitle>
        <CardDescription>
          展示合成结构中各槽位来自主样例或参考样例的归因说明。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span>
            主样例：
            <span className="ml-1 font-mono text-xs">{provenance.primarySampleId}</span>
          </span>
          {provenance.referenceSampleIds.length > 0 && (
            <Badge variant="secondary">
              参考 {provenance.referenceSampleIds.length} 个
            </Badge>
          )}
          {provenance.fallback && <Badge variant="outline">fallback</Badge>}
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "收起槽位归因" : "展开槽位归因"}
        </Button>
        <ul className="space-y-2 text-sm">
          {(expanded ? provenance.slotAttribution : preview).map((item) => (
            <li
              key={`${item.slotId}-${item.sourceSampleId}`}
              className="rounded-md border border-border p-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs">{item.slotId}</span>
                <Badge variant="outline">{item.sourceSampleId.slice(0, 8)}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{item.rationale}</p>
            </li>
          ))}
        </ul>
        {!expanded && provenance.slotAttribution.length > preview.length && (
          <p className="text-xs text-muted-foreground">
            还有 {provenance.slotAttribution.length - preview.length} 个槽位归因未展开。
          </p>
        )}
      </CardContent>
    </Card>
  );

}
