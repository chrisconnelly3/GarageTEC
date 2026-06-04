import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import GlobalBar from "./GlobalBar";

const baseProps = {
  players: [{ id: 1, name: "Chris", height_in: 72, handedness: "R" }],
  onSelectPlayer: vi.fn(),
};

describe("GlobalBar", () => {
  it("shows the R50 status chip text from status", () => {
    render(<GlobalBar {...baseProps}
      status={{ status: "connected", paused: false, shot_count: 3,
                active_player_id: 1 }}
      onPause={vi.fn()} onResume={vi.fn()} />);
    expect(screen.getByText(/connected/i)).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument();
  });

  it("renders Pause when running and calls onPause", () => {
    const onPause = vi.fn();
    render(<GlobalBar {...baseProps}
      status={{ status: "connected", paused: false, shot_count: 0,
                active_player_id: 1 }}
      onPause={onPause} onResume={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /pause/i }));
    expect(onPause).toHaveBeenCalled();
  });

  it("renders Resume and the paused label when paused", () => {
    const onResume = vi.fn();
    render(<GlobalBar {...baseProps}
      status={{ status: "paused", paused: true, shot_count: 0,
                active_player_id: 1 }}
      onPause={vi.fn()} onResume={onResume} />);
    expect(screen.getByText(/not recording/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /resume/i }));
    expect(onResume).toHaveBeenCalled();
  });
});
