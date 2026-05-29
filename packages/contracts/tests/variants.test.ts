import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  assertVariantsAllowed,
  getEnabledVariantIds,
  loadVariantRegistry,
} from "../src/variants.ts";

describe("variant registry", () => {
  it("loads all variants from registry.yaml", () => {
    const variants = loadVariantRegistry();
    const ids = variants.map((v) => v.id).sort();
    assert.deepEqual(ids, [
      "fast_paced",
      "high_click",
      "high_conversion",
      "premium",
    ]);
  });

  it("returns enabled variant ids high_click and high_conversion", () => {
    assert.deepEqual(getEnabledVariantIds(), ["high_click", "high_conversion"]);
  });

  it("assertVariantsAllowed accepts enabled ids", () => {
    assert.doesNotThrow(() =>
      assertVariantsAllowed(["high_click", "high_conversion"]),
    );
  });

  it("assertVariantsAllowed rejects unknown ids", () => {
    assert.throws(
      () => assertVariantsAllowed(["unknown_variant"]),
      /unknown_variant/,
    );
  });

  it("assertVariantsAllowed rejects disabled ids", () => {
    assert.throws(() => assertVariantsAllowed(["fast_paced"]), /fast_paced/);
  });
});
