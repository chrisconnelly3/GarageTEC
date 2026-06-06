import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { SwingDetail } from "../lib/types";

// ---------------------------------------------------------------------------
// Mock the api module before importing LiveScreen so all fetches are stubbed.
// ---------------------------------------------------------------------------
vi.mock("../lib/api", () => ({
  getLatestSwing: vi.fn(),
  getHistory: vi.fn(),
  getBallHistory: vi.fn(),
  mediaUrl: (path: string) => `/media/${path}`,
  getClubs: vi.fn(),
}));

import { LiveScreen } from "./LiveScreen";
import * as api from "../lib/api";

// ---------------------------------------------------------------------------
// Fixture: a realistic SwingDetail with benchmarks and ball data.
// ---------------------------------------------------------------------------
const mockSwing: SwingDetail = {
  swing: {
    id: 42, session_id: 1, player_id: 1, created_at: "2024-01-01T10:00:00Z",
    source_video_path: "swings/42.mp4", view_layout: null, fps: null,
    width: null, height: null, club: "7 Iron", notes: null, shot_id: 99,
  },
  metrics: [],
  benchmarks: [
    // context: "impact" — matches the default phase (currentPhase defaults to impact).
    {
      name: "shoulder_tilt_deg", context: "impact",
      value: 38, unit: "deg", target: 36, delta: 2, comparable: true,
      reason: null, direction: "higher", zone: "green", state: "ok",
    },
    // early_extension_in only at "address" context — won't show at impact phase.
    {
      name: "early_extension_in", context: "address",
      value: 0.5, unit: "in", target: 1.0, delta: -0.5, comparable: true,
      reason: null, direction: "lower", zone: "yellow", state: "ok",
    },
  ],
  ball_benchmarks: [
    {
      key: "ball_speed", label: "Ball Speed", unit: "mph",
      value: 142, target: 161, delta: -19, near: false,
      direction: "higher", zone: "red",
    },
  ],
  ball_raw: [],
  moments: [
    { id: 1, swing_id: 42, kind: "address", view: null, frame_index: 0, time_s: 0 },
    { id: 2, swing_id: 42, kind: "impact",  view: null, frame_index: 30, time_s: 1.0 },
  ],
  shot: {
    id: 99, swing_id: 42, player_id: 1, session_id: 1,
    captured_at: "2024-01-01T10:00:00Z", device_id: null, shot_number: 1,
    ball_speed: 142, total_spin: 6200, spin_axis: 2, hla: 0, vla: 14,
    carry: 180, club_speed: 95, attack_angle: -5, club_path: 2,
    face_to_target: 1, club: "7 Iron",
  },
  coaching: [],
  media: [{ id: 1, swing_id: 42, kind: "annotated_video", path: "swings/42_ann.mp4", meta: null }],
};

describe("LiveScreen", () => {
  beforeEach(() => {
    vi.mocked(api.getLatestSwing).mockResolvedValue(mockSwing);
    vi.mocked(api.getHistory).mockResolvedValue({ player: 1, metric: "shoulder_tilt_deg", context: "impact", points: [] });
    vi.mocked(api.getBallHistory).mockResolvedValue({ player: 1, metric: "ball_speed", club: "7 Iron", target: 161, points: [] });
    vi.mocked(api.getClubs).mockResolvedValue(["Driver", "7 Iron"]);
  });

  it("renders benchmarked body card with value and tour line once data loads", async () => {
    render(
      <LiveScreen
        playerId={1}
        sessionId={1}
        lastSwing={null}
        lastCapture={null}
        activeClub="7 Iron"
      />,
    );
    // After async load, the shoulder tilt card should appear.
    const valueEl = await screen.findByText("38");
    expect(valueEl).toBeInTheDocument();
    // Tour target should be shown.
    expect(screen.getByText(/Tour 36/)).toBeInTheDocument();
  });

  it("renders off-phase metric placeholder for metrics without a benchmark at current phase", async () => {
    // early_extension_in is in benchmarks only at "address"; the default phase
    // is impact so it won't have a benchmark match there.
    render(
      <LiveScreen
        playerId={1}
        sessionId={1}
        lastSwing={null}
        lastCapture={null}
        activeClub="7 Iron"
      />,
    );
    // Wait for data to load.
    await screen.findByText("38");
    // Early Ext. should be rendered as off-phase or raw because no benchmark
    // exists for early_extension_in at the "impact" context in our fixture.
    expect(screen.getByText(/Early Ext\./i)).toBeInTheDocument();
  });

  it("renders ball speed card from ball_benchmarks", async () => {
    render(
      <LiveScreen
        playerId={1}
        sessionId={1}
        lastSwing={null}
        lastCapture={null}
        activeClub="7 Iron"
      />,
    );
    // Ball Speed card should show value 142.
    expect(await screen.findByText("142")).toBeInTheDocument();
    // Tour target line.
    expect(screen.getByText(/Tour 161/)).toBeInTheDocument();
  });

  it("shows pick-club explanation when no activeClub and no ball cards", async () => {
    // Use a swing with no ball_benchmarks so the empty state triggers.
    vi.mocked(api.getLatestSwing).mockResolvedValue({
      ...mockSwing,
      ball_benchmarks: [],
      ball_raw: [],
    });
    render(
      <LiveScreen
        playerId={1}
        sessionId={1}
        lastSwing={null}
        lastCapture={null}
        activeClub={null}
      />,
    );
    await screen.findByText("38");
    expect(screen.getByText(/pick the club you're hitting/i)).toBeInTheDocument();
  });

  it("defaults currentPhase to impact (shows impact benchmark cards before any video plays)", async () => {
    // With videoTime=0 and no manualPhase, currentPhase must be 'impact'.
    // The fixture has shoulder_tilt_deg at context:"impact" so its value (38) must appear.
    render(
      <LiveScreen
        playerId={1}
        sessionId={1}
        lastSwing={null}
        lastCapture={null}
        activeClub="7 Iron"
      />,
    );
    // value=38 is the impact benchmark — it should show without any video interaction.
    expect(await screen.findByText("38")).toBeInTheDocument();
    // The phase label(s) in the body section should say "impact" (may appear more than once).
    expect(screen.getAllByText("impact").length).toBeGreaterThan(0);
  });

  it("does NOT render the FirstRunPrimer (removed from Live)", async () => {
    localStorage.clear();
    render(
      <LiveScreen
        playerId={1}
        sessionId={1}
        lastSwing={null}
        lastCapture={null}
        activeClub="7 Iron"
      />,
    );
    await screen.findByText("38");
    expect(screen.queryByTestId("first-run-primer")).not.toBeInTheDocument();
  });

  it("renders the captured view without an outer scroll container (fits one viewport)", async () => {
    const { container } = render(
      <LiveScreen
        playerId={1}
        sessionId={1}
        lastSwing={null}
        lastCapture={null}
        activeClub="7 Iron"
      />,
    );
    await screen.findByText("38");
    // The outer Live container must not scroll — it should fit, not overflow-y-auto.
    const outer = container.firstElementChild as HTMLElement;
    expect(outer.className).toContain("overflow-hidden");
    expect(outer.className).not.toContain("overflow-y-auto");
  });

  it("shows waiting state when no swing data", async () => {
    vi.mocked(api.getLatestSwing).mockResolvedValue(null);
    render(
      <LiveScreen
        playerId={1}
        sessionId={1}
        lastSwing={null}
        lastCapture={null}
        activeClub={null}
      />,
    );
    expect(await screen.findByText(/waiting for your r50/i)).toBeInTheDocument();
  });
});
