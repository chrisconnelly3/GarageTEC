import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import MetricCard from "./MetricCard";

describe("MetricCard", () => {
  it("renders value, unit, and vs-baseline / vs-ideal", () => {
    render(
      <MetricCard
        name="hip_sway_in"
        value={2.5}
        unit="in"
        vsBaseline={+0.4}
        vsIdeal={-0.6}
      />
    );
    expect(screen.getByText("hip_sway_in")).toBeInTheDocument();
    expect(screen.getByText(/2\.5\s*in/)).toBeInTheDocument();
    expect(screen.getByText(/baseline/i)).toBeInTheDocument();
    expect(screen.getByText(/ideal/i)).toBeInTheDocument();
  });

  it("shows a low-confidence flag when confidence is low", () => {
    render(<MetricCard name="tempo" value={3.1} unit="r" lowConfidence />);
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument();
  });

  it("omits the flag when confidence is fine", () => {
    render(<MetricCard name="tempo" value={3.1} unit="r" />);
    expect(screen.queryByText(/low confidence/i)).toBeNull();
  });
});
