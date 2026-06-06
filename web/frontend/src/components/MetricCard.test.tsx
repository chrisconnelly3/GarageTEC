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
  it("zone reads via tinted border + wash + dot, NOT a side-stripe", () => {
    const { container } = render(<MetricCard label="Shoulder Tilt" phase="top"
      value={38} unit="deg" target={36} delta={2} zone="green" state="ok"
      trend={{ delta: 1.2, towardPro: true }} />);
    const card = container.firstElementChild as HTMLElement;
    // Full tinted border + faint wash carry the zone — no banned left stripe.
    expect(card.className).toContain("border-garage-green/40");
    expect(card.className).toContain("bg-garage-green/[0.08]");
    expect(card.className).not.toContain("border-l-4");
    // Leading zone dot present.
    expect(container.querySelector(".bg-garage-green.rounded-full")).not.toBeNull();
  });
  it("unknown unit (method/confidence string) renders NO garbage suffix", () => {
    render(<MetricCard label="Spine Angle" phase="impact" value={42} isEstimated
      unit="foreshortening_2d;confidence=low" target={40} delta={2}
      zone="green" state="ok" trend={{ delta: 0, towardPro: null }} />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.queryByText(/foreshortening_2d/)).toBeNull();
    expect(screen.queryByText(/confidence=low/)).toBeNull();
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
  it("compact mode: dense padding + smaller value, still shows value/tour", () => {
    const { container } = render(<MetricCard label="Shoulder Tilt" value={38} unit="deg"
      target={36} delta={2} zone="green" state="ok" compact
      trend={{ delta: 1.2, towardPro: true }} />);
    const card = container.firstElementChild as HTMLElement;
    // Dense padding (p-2.5) and smaller value (text-xl), not the full p-4/text-3xl.
    expect(card.className).toContain("p-2.5");
    expect(card.className).not.toContain("p-4");
    const value = screen.getByText("38");
    expect(value.className).toContain("text-xl");
    expect(value.className).not.toContain("text-3xl");
    expect(screen.getByText(/Tour 36/)).toBeInTheDocument();
  });
  it("non-compact (default) keeps the fuller card size for Review/History", () => {
    const value = render(<MetricCard label="Shoulder Tilt" value={38} unit="deg"
      target={36} delta={2} zone="green" state="ok"
      trend={{ delta: 1.2, towardPro: true }} />).getByText("38");
    expect(value.className).toContain("text-3xl");
  });
});
