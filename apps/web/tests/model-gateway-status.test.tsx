import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ProjectsPage from "@/app/projects/page";
import { ModelGatewayStatusPanel } from "@/features/settings/ModelGatewayStatusPanel";
import { fixtureModelGatewayStatus } from "@/fixtures";
import * as apiClient from "@/lib/apiClient";

describe("ModelGatewayStatusPanel", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getModelGatewayStatus").mockResolvedValue({
      data: fixtureModelGatewayStatus,
      meta: { dataSource: "fixture" },
    });
    vi.spyOn(apiClient, "updateModelGatewaySettings").mockResolvedValue({
      data: fixtureModelGatewayStatus,
      meta: { dataSource: "fixture" },
    });
    vi.spyOn(apiClient, "listProjects").mockResolvedValue({
      data: { projects: [] },
      meta: { dataSource: "fixture" },
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows summary chips when collapsed", async () => {
    render(<ModelGatewayStatusPanel />);

    await waitFor(() =>
      expect(screen.getByTestId("model-gateway-status-panel")).toBeInTheDocument(),
    );

    expect(screen.getByText("Fixture 模式")).toBeInTheDocument();
    expect(screen.getByText("文本")).toBeInTheDocument();
    expect(screen.getByText("生图")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "保存配置" })).not.toBeInTheDocument();
  });

  it("expands to show configuration form", async () => {
    const user = userEvent.setup();
    render(<ModelGatewayStatusPanel />);

    await waitFor(() => expect(screen.getByText("模型服务")).toBeInTheDocument());

    await user.click(
      screen.getByRole("button", { name: "展开模型服务配置" }),
    );

    expect(await screen.findByRole("button", { name: "保存配置" })).toBeInTheDocument();
    expect(screen.getByLabelText("Model", { selector: "#text-model" })).toBeInTheDocument();
  });

  it("shows warning when required providers are missing in live mode", async () => {
    vi.mocked(apiClient.getModelGatewayStatus).mockResolvedValue({
      data: {
        fixtureMode: false,
        providers: {
          ...fixtureModelGatewayStatus.providers,
          text: {
            configured: false,
            hasApiKey: false,
            driver: "openai_compatible",
            baseUrl: "https://api.openai.com/v1",
          },
          image: {
            configured: false,
            hasApiKey: false,
            driver: "openai_compatible",
            baseUrl: "https://api.openai.com/v1",
          },
        },
      },
      meta: { dataSource: "api" },
    });

    render(<ModelGatewayStatusPanel />);

    await waitFor(() =>
      expect(
        screen.getByText(/Live 演示前请展开并配置文本、生图等凭据/),
      ).toBeInTheDocument(),
    );
  });

  it("saves provider settings via PUT when expanded", async () => {
    const user = userEvent.setup();
    render(<ModelGatewayStatusPanel defaultExpanded />);

    const textModel = await screen.findByLabelText("Model", {
      selector: "#text-model",
    });
    await user.clear(textModel);
    await user.type(textModel, "gpt-4o-new");

    const panel = screen.getByTestId("model-gateway-status-panel");
    await user.click(within(panel).getByRole("button", { name: "保存配置" }));

    await waitFor(() =>
      expect(apiClient.updateModelGatewaySettings).toHaveBeenCalled(),
    );

    const call = vi.mocked(apiClient.updateModelGatewaySettings).mock.calls[0]![0];
    expect(call.providers?.text?.model).toBe("gpt-4o-new");
    expect(call.providers?.text?.apiKey).toBeUndefined();
  });
});

describe("ProjectsPage model settings entry", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getModelGatewayStatus").mockResolvedValue({
      data: fixtureModelGatewayStatus,
      meta: { dataSource: "fixture" },
    });
    vi.spyOn(apiClient, "listProjects").mockResolvedValue({
      data: { projects: [] },
      meta: { dataSource: "fixture" },
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders model gateway panel on projects list page", async () => {
    render(<ProjectsPage />);

    await waitFor(() =>
      expect(screen.getByTestId("model-gateway-status-panel")).toBeInTheDocument(),
    );
    expect(screen.getByRole("heading", { name: "项目" })).toBeInTheDocument();
  });
});
