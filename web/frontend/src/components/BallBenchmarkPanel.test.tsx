import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BallBenchmarkPanel } from "./BallBenchmarkPanel";
import type { BallBenchmark } from "../lib/types";

const rows: BallBenchmark[] = [
  { key: "ball_speed", label: "Ball speed", unit: "mph", value: 118, target: 120, delta: -2, near: true },
  { key: "spin", label: "Spin rate", unit: "rpm", value: 7600, target: 7097, delta: 503, near: false },
];

describe("BallBenchmarkPanel", () => {
  it("renders rows with value / target / delta", () => {
    render(<BallBenchmarkPanel ball={rows} club="7 Iron" />);
    expect(screen.getByText(/Ball vs Tour Pro/i)).toBeTruthy();
    expect(screen.getByText("Ball speed")).toBeTruthy();
    expect(screen.getByText("-2 mph")).toBeTruthy();        // delta
    expect(screen.getByText(/7 Iron/)).toBeTruthy();
  });
  it("prompts to select a club when empty + no club", () => {
    render(<BallBenchmarkPanel ball={[]} club={null} />);
    expect(screen.getByText(/Select the club/i)).toBeTruthy();
  });
});
