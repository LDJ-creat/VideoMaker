import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ModelGatewayStatusPanel } from "@/features/settings/ModelGatewayStatusPanel";
import { fixtureModelGatewayStatus } from "@/fixtures";
import * as apiClient from "@/lib/apiClient";

describe("ModelGatewayStatusPanel", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getModelGatewayStatus").mockResolvedValue({
      data: fixtureModelGatewayStatus,
      meta: { dataSource: "fixture" },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows provider status and fixture badge", async () => {
    render(<ModelGatewayStatusPanel />);

    await waitFor(() =>
      expect(screen.getByTestId("model-gateway-status-panel")).toBeInTheDocument(),
    );

    expect(screen.getByText("Fixture 模式")).toBeInTheDocument();
    expect(screen.getByText("文本")).toBeInTheDocument();
    expect(screen.getAllByText("gpt-4o").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("dall-e-3")).toBeInTheDocument();
    expect(screen.getAllByText("未配置").length).toBeGreaterThanOrEqual(1);
  });

  it("shows warning when required providers are missing", async () => {
    vi.mocked(apiClient.getModelGatewayStatus).mockResolvedValue({
      data: {
        fixtureMode: false,
        providers: {
          ...fixtureModelGatewayStatus.providers,
          text: { configured: false, driver: "openai_compatible" },
          image: { configured: false, driver: "openai_compatible" },
        },
      },
      meta: { dataSource: "api" },
    });

    render(<ModelGatewayStatusPanel />);

    await waitFor(() =>
      expect(
        screen.getByText(/模型服务未就绪，请在服务端配置环境变量/),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/TEXT_API_KEY/)).toBeInTheDocument();
  });
});
