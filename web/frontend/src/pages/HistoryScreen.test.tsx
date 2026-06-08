import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("../lib/api", () => ({
  getHistory: vi.fn(),
  getBallHistory: vi.fn(),
  getClubs: vi.fn(),
}));

import { HistoryScreen } from "./HistoryScreen";
import * as api from "../lib/api";

const emptyHistory = { player: 1, metric: "shoulder_tilt_deg", context: "impact", target: null, points: [] };

describe("HistoryScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getHistory).mockResolvedValue(emptyHistory);
    vi.mocked(api.getBallHistory).mockResolvedValue({ player: 1, metric: "ball_speed", club: "Driver", target: 161, points: [] });
    vi.mocked(api.getClubs).mockResolvedValue(["Driver", "7 Iron"]);
  });

  it("renders the metric select with options from BODY_CARD_ORDER (minus hand_depth_in)", async () => {
    render(<HistoryScreen playerId={1} onOpenSwing={() => {}} />);
    const select = await screen.findByTestId("metric-select");
    expect(select).toBeInTheDocument();
    // Should contain shoulder_tilt_deg option (label "Shoulder Tilt")
    expect(screen.getByRole("option", { name: /shoulder tilt/i })).toBeInTheDocument();
    // hand_depth_in is excluded (it's raw-only)
    expect(screen.queryByRole("option", { name: /hand depth/i })).not.toBeInTheDocument();
  });

  it("renders the context select with address/top/impact options", async () => {
    render(<HistoryScreen playerId={1} onOpenSwing={() => {}} />);
    const select = await screen.findByTestId("context-select");
    expect(select).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /address/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /top/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /impact/i })).toBeInTheDocument();
  });

  it("changing the metric select triggers a new getHistory call with the new metric", async () => {
    render(<HistoryScreen playerId={1} onOpenSwing={() => {}} />);
    const select = await screen.findByTestId("metric-select");
    // Default fetch: shoulder_tilt_deg, impact
    expect(api.getHistory).toHaveBeenCalledWith(1, "shoulder_tilt_deg", "impact");

    // Change to hip_sway_in
    fireEvent.change(select, { target: { value: "hip_sway_in" } });
    expect(await screen.findByRole("option", { name: /hip sway/i, selected: true } as Parameters<typeof screen.findByRole>[1])).toBeInTheDocument();
    expect(api.getHistory).toHaveBeenCalledWith(1, "hip_sway_in", "impact");
  });

  it("changing the context select triggers a new getHistory call with the new context", async () => {
    render(<HistoryScreen playerId={1} onOpenSwing={() => {}} />);
    const select = await screen.findByTestId("context-select");
    // Default: impact
    expect(api.getHistory).toHaveBeenCalledWith(1, "shoulder_tilt_deg", "impact");

    // Change to address
    fireEvent.change(select, { target: { value: "address" } });
    expect(api.getHistory).toHaveBeenCalledWith(1, "shoulder_tilt_deg", "address");
  });

  it("shows a timeframe-aware empty state when chart data is empty", async () => {
    render(<HistoryScreen playerId={1} onOpenSwing={() => {}} />);
    expect(await screen.findByText(/no shots in this month yet/i)).toBeInTheDocument();
  });

  it("does not call getHistory when playerId is null", () => {
    render(<HistoryScreen playerId={null} onOpenSwing={() => {}} />);
    // The selects should render (the controls are always visible)
    expect(screen.getByTestId("metric-select")).toBeInTheDocument();
    // But no fetch should fire because playerId is null
    expect(api.getHistory).not.toHaveBeenCalled();
  });
});
