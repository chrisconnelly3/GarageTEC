import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FirstRunPrimer } from "./FirstRunPrimer";

describe("FirstRunPrimer", () => {
  it("renders the title and all three bullet points", () => {
    render(<FirstRunPrimer onDismiss={vi.fn()} />);
    expect(screen.getByText(/reading your swing/i)).toBeInTheDocument();
    expect(screen.getByText(/each card compares you to a tour pro/i)).toBeInTheDocument();
    expect(screen.getByText(/tap address, top, or impact/i)).toBeInTheDocument();
    expect(screen.getByText(/needs 3d/i)).toBeInTheDocument();
  });

  it("calls onDismiss when the X button is clicked", () => {
    const onDismiss = vi.fn();
    render(<FirstRunPrimer onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("has a data-testid for integration tests", () => {
    render(<FirstRunPrimer onDismiss={vi.fn()} />);
    expect(screen.getByTestId("first-run-primer")).toBeInTheDocument();
  });
});
