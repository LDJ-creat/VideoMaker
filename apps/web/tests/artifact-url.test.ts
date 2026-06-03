import { describe, expect, it } from "vitest";

import {
  generationCompositionPreviewUrl,
  generationRenderPreviewUrl,
  generationRenderVideoUrl,
} from "@/lib/artifactUrl";

describe("generation render media URLs", () => {
  it("builds composition index.html path under project media file route", () => {
    expect(
      generationCompositionPreviewUrl(
        "065c5165-f0d8-4e1e-acbb-59c92778391a",
        "ab628531-0a05-40ac-b4e1-bd377233ece2",
      ),
    ).toBe(
      "/api/projects/065c5165-f0d8-4e1e-acbb-59c92778391a/media/file/renders/ab628531-0a05-40ac-b4e1-bd377233ece2/composition/index.html",
    );
  });

  it("builds preview.html path under project media file route", () => {
    expect(
      generationRenderPreviewUrl(
        "065c5165-f0d8-4e1e-acbb-59c92778391a",
        "ab628531-0a05-40ac-b4e1-bd377233ece2",
      ),
    ).toBe(
      "/api/projects/065c5165-f0d8-4e1e-acbb-59c92778391a/media/file/renders/ab628531-0a05-40ac-b4e1-bd377233ece2/preview.html",
    );
  });

  it("builds output.mp4 path under project media file route", () => {
    expect(
      generationRenderVideoUrl("proj-1", "gen-1"),
    ).toBe("/api/projects/proj-1/media/file/renders/gen-1/output.mp4");
  });
});
