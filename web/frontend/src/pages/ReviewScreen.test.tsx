import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import type { SwingDetail, SwingSummary } from "../lib/types";

// ---------------------------------------------------------------------------
// Mock the api module.
// ---------------------------------------------------------------------------
vi.mock("../lib/api", () => ({
  getSwing: vi.fn(),
  getSwings: vi.fn(),
  getBallHistory: vi.fn(),
  mediaUrl: (path: string) => `/media/${path}`,
}));

import { ReviewScreen } from "./ReviewScreen";
import * as api from "../lib/api";

// ---------------------------------------------------------------------------
// Fixtures.
// ---------------------------------------------------------------------------
const makeSwingDetail = (id: number, shoulderTilt = 38): SwingDetail => ({
  swing: {
    id, session_id: 1, player_id: 1, created_at: "2024-01-01T10:00:00Z",
    source_video_path: null, view_layout: null, fps: null,
    width: null, height: null, club: "Driver", notes: null, shot_id: null,
  },
  metrics: [],
  benchmarks: [
    {
      name: "shoulder_tilt_deg", context: "address",
      value: shoulderTilt, unit: "deg", target: 36, delta: shoulderTilt - 36,
      comparable: true, reason: null, direction: "higher",
      zone: "green", state: "ok",
    },
  ],
  ball_benchmarks: [
    {
      key: "ball_speed", label: "Ball Speed", unit: "mph",
      value: 150, target: 161, delta: -11, near: false,
      direction: "higher", zone: "yellow",
    },
  ],
  ball_raw: [],
  moments: [
    { id: 1, swing_id: id, kind: "address", view: null, frame_index: 0, time_s: 0 },
    { id: 2, swing_id: id, kind: "impact",  view: null, frame_index: 30, time_s: 1.0 },
  ],
  shot: {
    id: 1, swing_id: id, player_id: 1, session_id: 1,
    captured_at: "2024-01-01T10:00:00Z", device_id: null, shot_number: 1,
    ball_speed: 150, total_spin: 5800, spin_axis: 1, hla: 0, vla: 12,
    carry: 260, club_speed: 110, attack_angle: 2, club_path: 1,
    face_to_target: 0, club: "Driver",
  },
  coaching: [],
  media: [],
});

const swingSummaries: SwingSummary[] = [
  { id: 10, created_at: "2024-01-01T10:05:00Z", club: "Driver", has_shot: true, hip_sway_in: 1.2, shoulder_tilt_deg: 38 },
  { id: 11, created_at: "2024-01-01T10:10:00Z", club: "Driver", has_shot: false, hip_sway_in: 1.0, shoulder_tilt_deg: 40 },
];

describe("ReviewScreen", () => {
  beforeEach(() => {
    vi.mocked(api.getSwings).mockResolvedValue(swingSummaries);
    vi.mocked(api.getSwing).mockImplementation((id) =>
      Promise.resolve(makeSwingDetail(id)),
    );
    vi.mocked(api.getBallHistory).mockResolvedValue({
      player: 1, metric: "ball_speed", club: "Driver", target: 161, points: [],
    });
  });

  it("renders body table with a zone-colored cell (green class for green zone)", async () => {
    render(
      <ReviewScreen
        playerId={1}
        sessionId={1}
        defaultSwingId={10}
      />,
    );
    // Wait for the swing to load: Shoulder Tilt value 38° should appear.
    // The cell() function renders value+unit suffix together: "38°".
    const valueEl = await screen.findByText("38°");
    expect(valueEl).toBeInTheDocument();
    // The value span should carry the green text class.
    expect(valueEl).toHaveClass("text-garage-green");
  });

  it("renders ball benchmark card (Ball Speed)", async () => {
    render(
      <ReviewScreen
        playerId={1}
        sessionId={1}
        defaultSwingId={10}
      />,
    );
    // Wait for swing to load; shoulder tilt cell renders "38°".
    await screen.findByText("38°");
    // Ball Speed card value (MetricCard renders number then separate unit span).
    expect(screen.getByText("150")).toBeInTheDocument();
    // Tour target line inside MetricCard.
    expect(screen.getByText(/tour 161/i)).toBeInTheDocument();
  });

  it("shows 'no matched ball data' when ball_benchmarks is empty", async () => {
    vi.mocked(api.getSwing).mockResolvedValue({
      ...makeSwingDetail(10),
      ball_benchmarks: [],
      ball_raw: [],
      shot: null,
    });
    render(
      <ReviewScreen
        playerId={1}
        sessionId={1}
        defaultSwingId={10}
      />,
    );
    await screen.findByText(/no matched ball data/i);
    expect(screen.getByText(/no matched ball data/i)).toBeInTheDocument();
  });

  it("Fix 2: manual selection is NOT overridden by a new defaultSwingId", async () => {
    // We'll render with defaultSwingId=10 initially, then the user picks swing 11,
    // then a new defaultSwingId=10 re-arrives (simulating a live SSE event).
    // The shown swing must stay at 11.
    vi.mocked(api.getSwing).mockImplementation((id) =>
      Promise.resolve(makeSwingDetail(id, id === 10 ? 38 : 55)),
    );

    const { rerender } = render(
      <ReviewScreen
        playerId={1}
        sessionId={1}
        defaultSwingId={10}
      />,
    );

    // Wait for initial swing 10 to load. Cell renders value as "38°".
    await screen.findByText("38°");

    // User manually selects swing 11 from the picker.
    const picker = screen.getByRole("combobox");
    await act(async () => {
      fireEvent.change(picker, { target: { value: "11" } });
    });

    // Swing 11 has shoulderTilt=55; wait for it to render as "55°".
    await screen.findByText("55°");

    // Now simulate a new defaultSwingId arriving (e.g. latest swing is still 10).
    await act(async () => {
      rerender(
        <ReviewScreen
          playerId={1}
          sessionId={1}
          defaultSwingId={10}
        />,
      );
    });

    // The displayed swing must still be 11 (tilt=55°), NOT reverted to 10 (tilt=38°).
    expect(screen.getByText("55°")).toBeInTheDocument();
    expect(screen.queryByText("38°")).not.toBeInTheDocument();
  });
});
