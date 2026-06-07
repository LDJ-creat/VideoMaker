import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GeneratedAssetBadge } from "@/features/aigc-preview/GeneratedAssetBadge";

describe("GeneratedAssetBadge stock media", () => {
  it("renders Pexels label and attribution tooltip", () => {
    render(
      <GeneratedAssetBadge
        provider="stock_media_search"
        generatedBy={{
          provider: "stock_media_search",
          source: "pexels",
          photographer: "Jane Doe",
          pageUrl: "https://www.pexels.com/photo/123/",
        }}
      />,
    );
    expect(screen.getByTestId("generated-asset-badge")).toHaveTextContent("Pexels 素材");
    expect(screen.getByTestId("generated-asset-badge")).toHaveAttribute(
      "title",
      expect.stringContaining("Jane Doe"),
    );
  });
});
