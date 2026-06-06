import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useApi } from "./useApi";

describe("useApi", () => {
  it("loads and exposes data", async () => {
    const fn = vi.fn().mockResolvedValue("hello");
    const { result } = renderHook(() => useApi(fn));
    expect(result.current.loading).toBe(true);
    await act(async () => {});
    expect(result.current.data).toBe("hello");
    expect(result.current.loading).toBe(false);
  });

  it("reload() – stale out-of-order response is discarded; latest wins", async () => {
    // Two promises we control manually.
    let resolveFirst!: (v: string) => void;
    let resolveSecond!: (v: string) => void;
    const first = new Promise<string>((r) => { resolveFirst = r; });
    const second = new Promise<string>((r) => { resolveSecond = r; });

    let callCount = 0;
    const fn = vi.fn().mockImplementation(() => {
      callCount++;
      return callCount === 1 ? first : second;
    });

    const { result } = renderHook(() => useApi(fn));

    // Trigger first load (the effect fires automatically).
    // Now trigger a second load before the first resolves.
    act(() => { result.current.reload(); });

    // Resolve the FIRST (older) promise after the second has been dispatched.
    await act(async () => { resolveFirst("stale-value"); });
    // The stale value must NOT appear because a newer generation exists.
    expect(result.current.data).not.toBe("stale-value");

    // Now resolve the second (latest) promise.
    await act(async () => { resolveSecond("fresh-value"); });
    expect(result.current.data).toBe("fresh-value");
    expect(result.current.loading).toBe(false);
  });
});
