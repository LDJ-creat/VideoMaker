"use client";

import { ModelGatewayStatusPanel } from "@/features/settings/ModelGatewayStatusPanel";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 pb-10">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">全局设置</h1>
        <p className="mt-1 text-muted-foreground">
          管理模型服务及应用程序的其他偏好设置。
        </p>
      </div>

      <ModelGatewayStatusPanel defaultExpanded />
    </div>
  );
}
