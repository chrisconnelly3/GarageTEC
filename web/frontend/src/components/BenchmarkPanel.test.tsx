import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BenchmarkPanel } from "./BenchmarkPanel";
import type { Benchmark } from "../lib/types";

const rows: Benchmark[] = [
  { name: "shoulder_tilt_deg", context: "address", value: 11, unit: "deg",
    target: 10, delta: 1, comparable: true, reason: null },
  { name: "shoulder_turn_deg", context: "top", value: 50, unit: "deg",
    target: 89, delta: null, comparable: false, reason: "needs_3d" },
];

describe("BenchmarkPanel", () => {
  it("renders title and a comparable row with delta", () => {
    render(<BenchmarkPanel benchmarks={rows} />);
    expect(screen.getByText(/vs Tour Pro/i)).toBeTruthy();
    expect(screen.getByText("Shoulder tilt")).toBeTruthy();
    expect(screen.getByText("+1°")).toBeTruthy();      // delta
  });
  it("shows a needs-3D badge for gated metrics + the footnote", () => {
    render(<BenchmarkPanel benchmarks={rows} />);
    expect(screen.getAllByText(/needs 3D/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/light up once/i)).toBeTruthy();
  });
  it("handles empty benchmarks", () => {
    render(<BenchmarkPanel benchmarks={[]} />);
    expect(screen.getByText(/No tour-pro comparisons/i)).toBeTruthy();
  });
});
