import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AIInsightCard } from "./AIInsightCard";

const insights = [
  {
    id: "0",
    type: "mechanic" as const,
    text: "+1 deg vs your recent average",
    metric: "Shoulder Tilt",
    drill: "Wall drill",
    severity: "neutral" as const,
  },
];

describe("AIInsightCard", () => {
  it("renders the headline", () => {
    render(<AIInsightCard headline="Strong impact position" insights={insights} />);
    expect(screen.getByText("Strong impact position")).toBeInTheDocument();
  });
  it("renders the summary narrative under the headline when present", () => {
    render(
      <AIInsightCard
        headline="Strong impact position"
        summary="Your tilt is tracking nicely toward tour. Keep the same setup and trust the lower body."
        insights={insights}
      />,
    );
    expect(screen.getByText(/tracking nicely toward tour/i)).toBeInTheDocument();
  });
  it("omits the summary block when summary is null/absent", () => {
    render(<AIInsightCard headline="Headline only" summary={null} insights={insights} />);
    expect(screen.queryByText(/tracking nicely/i)).not.toBeInTheDocument();
  });
  it("still renders the bullet findings (delta + drill)", () => {
    render(<AIInsightCard headline="H" summary="S" insights={insights} />);
    expect(screen.getByText(/\+1 deg vs your recent average/)).toBeInTheDocument();
    expect(screen.getByText(/Wall drill/)).toBeInTheDocument();
  });
});
