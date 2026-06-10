import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkbenchToast } from "@/components/workbench/WorkbenchToast";

describe("WorkbenchToast", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows message and auto dismisses", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();

    render(<WorkbenchToast message="Brief 已保存" onDismiss={onDismiss} durationMs={2000} />);

    expect(screen.getByRole("status")).toHaveTextContent("Brief 已保存");

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
