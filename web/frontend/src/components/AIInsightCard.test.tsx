import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AIInsightCard } from "./AIInsightCard";

describe("AIInsightCard", () => {
  it("renders the headline", () => {
    render(<AIInsightCard headline="Strong impact position" />);
    expect(screen.getByText("Strong impact position")).toBeInTheDocument();
  });
  it("renders the summary body under the headline when present", () => {
    render(
      <AIInsightCard
        headline="Strong impact position"
        summary="Your biggest leak is an open face. Spine angle is steep at the top too."
      />,
    );
    expect(screen.getByText(/biggest leak is an open face/i)).toBeInTheDocument();
  });
  it("omits the summary block when summary is null/absent", () => {
    render(<AIInsightCard headline="Headline only" summary={null} />);
    expect(screen.queryByText(/biggest leak/i)).not.toBeInTheDocument();
  });
});
