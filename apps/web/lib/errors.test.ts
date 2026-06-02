import { describe, expect, it } from "vitest";

import { formatFastApiDetail } from "./errors";

describe("formatFastApiDetail", () => {
  it("formats validation error arrays", () => {
    const detail = [
      {
        type: "value_error",
        loc: ["body", "providers", "text", "model"],
        msg: "model must be non-empty when provided for provider 'text'",
      },
    ];
    expect(formatFastApiDetail(detail)).toBe(
      "providers.text.model: model must be non-empty when provided for provider 'text'",
    );
  });

  it("returns string detail as-is", () => {
    expect(formatFastApiDetail("No provider fields to update")).toBe(
      "No provider fields to update",
    );
  });
});
