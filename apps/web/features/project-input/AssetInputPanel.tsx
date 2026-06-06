"use client";

import { useMemo, useState } from "react";

import { FileDropzone } from "@/components/file-dropzone";
import { PaginatedGrid } from "@/components/paginated-grid";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ProjectAsset } from "@/lib/apiClient";
import { uploadAsset } from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { validateAssetUploadSize } from "@/lib/validation";

const ASSET_PAGE_SIZE = 4;

type AssetFilter = "all" | "image" | "video" | "text";

type AssetInputPanelProps = {
  projectId: string;
  assets: ProjectAsset[];
  className?: string;
  onAssetsChanged?: () => void;
};

function AssetPreview({ asset }: { asset: ProjectAsset }) {
  if (asset.type === "text") {
    return (
      <p className="line-clamp-5 whitespace-pre-wrap text-xs text-muted-foreground">
        {asset.description ?? asset.uri}
      </p>
    );
  }
  if (!asset.previewUrl) {
    return (
      <p className="text-xs text-muted-foreground truncate">
        {asset.description ?? asset.uri}
      </p>
    );
  }
  if (asset.type === "image") {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={asset.previewUrl}
        alt={asset.description ?? asset.id}
        className="max-h-36 w-full rounded-md border border-border object-contain bg-muted/30"
      />
    );
  }
  if (asset.type === "video") {
    return (
      <video
        src={asset.previewUrl}
        controls
        className="max-h-36 w-full rounded-md border border-border bg-black"
      />
    );
  }
  return null;
}

function AssetCard({ asset }: { asset: ProjectAsset }) {
  return (
    <div className="space-y-2 rounded-lg border border-border p-3">
      <div className="flex items-center justify-between gap-2">
        <Badge variant="outline">{asset.type}</Badge>
        <span className="font-mono text-[10px] text-muted-foreground truncate">
          {asset.id}
        </span>
      </div>
      <AssetPreview asset={asset} />
      {asset.description && asset.type !== "text" && (
        <p className="text-xs text-muted-foreground truncate">
          {asset.description}
        </p>
      )}
    </div>
  );
}

export function AssetInputPanel({
  projectId,
  assets,
  className,
  onAssetsChanged,
}: AssetInputPanelProps) {
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [assetFilter, setAssetFilter] = useState<AssetFilter>("all");

  const imageCount = useMemo(
    () => assets.filter((asset) => asset.type === "image").length,
    [assets],
  );
  const videoCount = useMemo(
    () => assets.filter((asset) => asset.type === "video").length,
    [assets],
  );
  const textCount = useMemo(
    () => assets.filter((asset) => asset.type === "text").length,
    [assets],
  );

  const filteredAssets = useMemo(() => {
    if (assetFilter === "all") return assets;
    return assets.filter((asset) => asset.type === assetFilter);
  }, [assetFilter, assets]);

  const handleUpload = async (files: File[]) => {
    if (!files.length) return;
    setBusy(true);
    const names: string[] = [];
    try {
      for (const file of files) {
        const sizeError = validateAssetUploadSize(file);
        if (sizeError) {
          setStatus(sizeError);
          return;
        }
        const { data: result } = await uploadAsset(projectId, file);
        names.push(result.id);
      }
      setStatus(`已上传 ${names.length} 个素材`);
      onAssetsChanged?.();
    } catch (err) {
      setStatus(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className={cn("flex h-full flex-col", className)}>
      <CardHeader className="shrink-0">
        <CardTitle>用户素材</CardTitle>
        <CardDescription>
          Brief 描述创作意图，图片/视频/文案素材将一起用于统一理解
        </CardDescription>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-4">
        <FileDropzone
          accept="image/*,video/*,.txt,.md,text/plain,text/markdown"
          multiple
          disabled={busy}
          title="上传用户素材"
          hint="点击选择或拖拽图片、视频或文案（.txt / .md）到此处，支持批量上传"
          onFiles={(files) => void handleUpload(files)}
        />

        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <Tabs
            value={assetFilter}
            onValueChange={(value) => setAssetFilter(value as AssetFilter)}
            className="shrink-0"
          >
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="all">全部 ({assets.length})</TabsTrigger>
              <TabsTrigger value="image">图片 ({imageCount})</TabsTrigger>
              <TabsTrigger value="video">视频 ({videoCount})</TabsTrigger>
              <TabsTrigger value="text">文案 ({textCount})</TabsTrigger>
            </TabsList>
          </Tabs>

          <PaginatedGrid
            items={filteredAssets}
            pageSize={ASSET_PAGE_SIZE}
            resetKey={`${assetFilter}-${filteredAssets.map((asset) => asset.id).join(",")}`}
            getKey={(asset) => asset.id}
            renderItem={(asset) => <AssetCard asset={asset} />}
            emptyMessage={
              assetFilter === "all"
                ? "暂无素材，请上传图片、视频或文案。"
                : assetFilter === "image"
                  ? "暂无图片素材。"
                  : assetFilter === "video"
                    ? "暂无视频素材。"
                    : "暂无文案素材。"
            }
          />
        </div>

        {status && (
          <p className="shrink-0 text-sm text-muted-foreground" role="status">
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
