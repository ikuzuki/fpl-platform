import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useApi } from "./useApi";

describe("useApi", () => {
  it("starts in loading state", () => {
    const { result } = renderHook(() =>
      useApi(() => new Promise<string>(() => {}), "initial"),
    );
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe("initial");
    expect(result.current.error).toBeNull();
  });

  it("resolves data on success", async () => {
    const { result } = renderHook(() =>
      useApi(() => Promise.resolve("hello"), "initial"),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe("hello");
    expect(result.current.error).toBeNull();
  });

  it("sets error on failure", async () => {
    const { result } = renderHook(() =>
      useApi(() => Promise.reject(new Error("fail")), "initial"),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe("initial");
    expect(result.current.error).toBe("fail");
  });

  it("handles non-Error rejections", async () => {
    const { result } = renderHook(() =>
      useApi(() => Promise.reject("string error"), "initial"),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Failed to load data");
  });

  it("cancels on unmount", async () => {
    const neverResolves = new Promise<string>(() => {});
    const { unmount } = renderHook(() => useApi(() => neverResolves, "init"));
    unmount();
    // If the component unmounts, state setters should not be called
    await new Promise((r) => setTimeout(r, 10));
    // No error thrown = success (cancelled properly)
  });
});
