// web/frontend/src/pages/SwingScreen.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { SwingDetail, SwingSummary } from "../lib/types";

vi.mock("../lib/api", () => ({
  getLatestSwing: vi.fn(),
  getSwing: vi.fn(),
  getSwings: vi.fn(),
  getHistory: vi.fn(),
  getBallHistory: vi.fn(),
  mediaUrl: (p: string) => `/media/${p}`,
}));

import { SwingScreen } from "./SwingScreen";
import * as api from "../lib/api";

function mkDetail(
  id: number, opts: Partial<SwingDetail["swing"]> = {}, withVideo = true,
  extra: Partial<SwingDetail> = {},
): SwingDetail {
  return {
    swing: { id, session_id: 1, player_id: 1, created_at: "2024-01-01T10:00:00Z",
      source_video_path: null, view_layout: null, fps: null, width: null, height: null,
      club: "7 Iron", notes: null, shot_id: id === 42 ? 99 : null, ...opts },
    metrics: [],
    benchmarks: [{ name: "shoulder_tilt_deg", context: "impact", value: 38, unit: "deg",
      target: 36, delta: 2, comparable: true, reason: null, direction: "higher", zone: "green", state: "ok" }],
    ball_benchmarks: [{ key: "ball_speed", label: "Ball Speed", unit: "mph", value: 142,
      target: 161, delta: -19, near: false, direction: "higher", zone: "red" }],
    ball_raw: [],
    moments: [{ id: 1, swing_id: id, kind: "impact", view: null, frame_index: 30, time_s: 1.0 }],
    shot: null, coaching: [],
    media: withVideo ? [{ id: 1, swing_id: id, kind: "annotated_video", path: `${id}.mp4`, meta: null }] : [],
    ...extra,
  };
}
const summaries: SwingSummary[] = [
  { id: 42, created_at: "2024-01-01T10:02:00Z", club: "7 Iron", has_shot: true, hip_sway_in: null, shoulder_tilt_deg: null },
  { id: 41, created_at: "2024-01-01T10:01:00Z", club: "Driver", has_shot: true, hip_sway_in: null, shoulder_tilt_deg: null },
  { id: 40, created_at: "2024-01-01T10:00:00Z", club: "PW", has_shot: false, hip_sway_in: null, shoulder_tilt_deg: null },
];

const props = { playerId: 1, sessionId: 1, lastSwing: null, activeClub: "7 Iron",
  r50: "connected" as const, deepLinkSwingId: null, onReconnect: vi.fn() };

beforeEach(() => {
  vi.mocked(api.getLatestSwing).mockResolvedValue(mkDetail(42));
  vi.mocked(api.getSwing).mockImplementation((id: number) => Promise.resolve(mkDetail(id, {}, id !== 40)));
  vi.mocked(api.getSwings).mockResolvedValue(summaries);
  vi.mocked(api.getHistory).mockResolvedValue({ player: 1, metric: "shoulder_tilt_deg", context: "impact", target: null, points: [] });
  vi.mocked(api.getBallHistory).mockResolvedValue({ player: 1, metric: "ball_speed", club: "7 Iron", target: 161, points: [] });
});

describe("SwingScreen", () => {
  it("follows the latest swing by default", async () => {
    render(<SwingScreen {...props} />);
    expect(await screen.findByText("38")).toBeInTheDocument(); // body card from latest
    expect(api.getLatestSwing).toHaveBeenCalled();
  });

  it("pins a past swing when picked, loading getSwing", async () => {
    render(<SwingScreen {...props} />);
    await screen.findByText("38");
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "41" } });
    await waitFor(() => expect(api.getSwing).toHaveBeenCalledWith(41));
  });

  it("shows the new-shot count badge when pinned behind newer swings", async () => {
    render(<SwingScreen {...props} />);
    await screen.findByText("38");
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "40" } }); // 2 newer
    expect(await screen.findByTestId("new-count")).toHaveTextContent("2");
  });

  it("Go Live returns to following and clears the badge", async () => {
    render(<SwingScreen {...props} />);
    await screen.findByText("38");
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "40" } });
    await screen.findByTestId("new-count");
    fireEvent.click(screen.getByTestId("live-pill"));
    await waitFor(() => expect(screen.queryByTestId("new-count")).toBeNull());
  });

  it("shows the 'video not kept' placeholder for a pinned swing with no video", async () => {
    render(<SwingScreen {...props} />);
    await screen.findByText("38");
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "40" } }); // mkDetail(40) has no video
    expect(await screen.findByText("Video not kept for this swing")).toBeInTheDocument();
  });

  it("shows the R50-disconnected empty state with a Reconnect button", async () => {
    vi.mocked(api.getLatestSwing).mockResolvedValue(null);
    const onReconnect = vi.fn();
    render(<SwingScreen {...props} r50="error" onReconnect={onReconnect} />);
    const btn = await screen.findByText(/Reconnect/);
    fireEvent.click(btn);
    expect(onReconnect).toHaveBeenCalled();
  });

  it("opens deep-linked swing pinned", async () => {
    render(<SwingScreen {...props} deepLinkSwingId={41} />);
    await waitFor(() => expect(api.getSwing).toHaveBeenCalledWith(41));
  });

  it("disables Next for a pinned swing that is not in the list (deep-linked)", async () => {
    render(<SwingScreen {...props} deepLinkSwingId={99} />);
    await waitFor(() => expect(api.getSwing).toHaveBeenCalledWith(99));
    const next = await screen.findByLabelText("Newer swing");
    expect(next).toBeDisabled();
  });

  it("marks a ball card *est when its trust tier is estimated (spin -> total_spin)", async () => {
    vi.mocked(api.getLatestSwing).mockResolvedValue(mkDetail(42, {}, true, {
      ball_benchmarks: [{ key: "spin", label: "Spin Rate", unit: "rpm", value: 2200,
        target: 2545, delta: -345, near: false, direction: "lower", zone: "yellow" }],
      trust: { total_spin: "estimated" },
    }));
    render(<SwingScreen {...props} />);
    await screen.findByText("Spin Rate");
    expect(await screen.findByText("*est")).toBeInTheDocument();
  });

  it("does not mark a ball card when its trust tier is measured", async () => {
    vi.mocked(api.getLatestSwing).mockResolvedValue(mkDetail(42, {}, true, {
      ball_benchmarks: [{ key: "spin", label: "Spin Rate", unit: "rpm", value: 2200,
        target: 2545, delta: -345, near: false, direction: "lower", zone: "yellow" }],
      trust: { total_spin: "measured" },
    }));
    render(<SwingScreen {...props} />);
    await screen.findByText("Spin Rate");
    expect(screen.queryByText("*est")).toBeNull();
  });

  it("renders normally with no markers when trust is absent entirely", async () => {
    vi.mocked(api.getLatestSwing).mockResolvedValue(mkDetail(42)); // no `trust` field
    render(<SwingScreen {...props} />);
    await screen.findByText("Ball Speed");
    expect(screen.queryByText("*est")).toBeNull();
  });

  it("marks smash *est when either contributor (ball_speed/club_speed) isn't measured", async () => {
    vi.mocked(api.getLatestSwing).mockResolvedValue(mkDetail(42, {}, true, {
      ball_benchmarks: [{ key: "smash", label: "Smash Factor", unit: "", value: 1.3,
        target: 1.5, delta: -0.2, near: false, direction: "higher", zone: "yellow" }],
      trust: { ball_speed: "measured", club_speed: "estimated" },
    }));
    render(<SwingScreen {...props} />);
    await screen.findByText("Smash Factor");
    expect(await screen.findByText("*est")).toBeInTheDocument();
  });
});
