import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("benchmarked: shows value, tour line, delta", () => {
    render(<MetricCard label="Shoulder Tilt" phase="top" value={38} unit="deg"
      target={36} delta={2} zone="green" state="ok"
      trend={{ delta: 1.2, towardPro: true }} />);
    expect(screen.getByText("38")).toBeInTheDocument();
    expect(screen.getByText(/Tour 36/)).toBeInTheDocument();
  });
  it("needs_3d: shows NEEDS 3D, no delta", () => {
    render(<MetricCard label="Shoulder Turn" phase="top" value={84} unit="deg"
      target={89} delta={null} zone={null} state="needs_3d"
      trend={{ delta: 0, towardPro: null }} />);
    expect(screen.getByText(/NEEDS 3D/)).toBeInTheDocument();
  });
  it("raw: shows no tour avg", () => {
    render(<MetricCard label="Hand Depth" phase="impact" value={9.2} unit="in"
      target={null} delta={null} zone={null} state="raw"
      trend={{ delta: 0, towardPro: null }} />);
    expect(screen.getByText(/no tour avg/i)).toBeInTheDocument();
  });
  it("off-phase: dims with '— measured at'", () => {
    render(<MetricCard label="Early Ext." value={null} unit="in"
      target={0} delta={null} zone={null} state="ok" offPhase="impact"
      trend={{ delta: 0, towardPro: null }} />);
    expect(screen.getByText(/measured at impact/i)).toBeInTheDocument();
  });
});
