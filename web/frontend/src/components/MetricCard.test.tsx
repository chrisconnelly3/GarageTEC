import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("renders a metric name, value, and unit with demo props", () => {
    render(
      <MetricCard
        name="Shoulder Tilt"
        value={38}
        unit="deg"
        delta={2}
        deltaGood="up"
        idealRange={[35, 45]}
        currentNum={38}
      />
    );
    expect(screen.getByText(/Shoulder Tilt/i)).toBeInTheDocument();
    expect(screen.getByText("38")).toBeInTheDocument();
    expect(screen.getByText("deg")).toBeInTheDocument();
  });
});
