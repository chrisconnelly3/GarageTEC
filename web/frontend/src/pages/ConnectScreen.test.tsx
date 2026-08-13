import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const baseSettings = {
  idle_minutes: 15, units: "yards" as const, port: 921,
  has_api_key: false, api_key_hint: "",
};

vi.mock("../lib/api", () => ({
  getSettings: vi.fn(async () => baseSettings),
  putSettings: vi.fn(async () => baseSettings),
  restartCapture: vi.fn(async () => ({})),
  getSetupInfo: vi.fn(async () => ({
    lan_ip: "192.168.1.50", port: 921,
    openflight_connector: {
      connectors: [{
        type: "gspro", enabled: true, host: "192.168.1.50", port: 921,
        device_id: "OpenFlight",
      }],
    },
  })),
  // Pulled in transitively by CalibrationCard / LiveCaptureCard, both
  // rendered at the bottom of ConnectScreen.
  getCameras: vi.fn(async () => []),
  startCalibration: vi.fn(async () => ({ ok: true })),
  stopCalibration: vi.fn(async () => ({ ok: true })),
  runCalibration: vi.fn(async () => ({ ok: true })),
  getActiveCalibration: vi.fn(async () => null),
  getCalibrationHistory: vi.fn(async () => []),
  activateCalibration: vi.fn(async () => ({ ok: true })),
  startLiveCapture: vi.fn(async () => ({})),
  stopLiveCapture: vi.fn(async () => ({})),
  getLiveCaptureStatus: vi.fn(async () => ({
    running: false, capturing: false, source: "none",
    buffered_frames: 0, swing_count: 0, fps: 0, window_s: 4,
    post_shot_delay_s: 0.6, last_error: null,
  })),
}));

import { ConnectScreen } from "./ConnectScreen";
import * as api from "../lib/api";

describe("ConnectScreen — AI Coach card", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows how-to-get-a-key guidance", async () => {
    vi.mocked(api.getSettings).mockResolvedValue(baseSettings);
    render(<ConnectScreen captureStatus={null} />);
    expect(await screen.findByText(/How to get a key/i)).toBeTruthy();
    expect(screen.getByText(/console\.anthropic\.com/i)).toBeTruthy();
  });

  it("shows the masked hint (not the raw key) when a key is already stored", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({
      ...baseSettings, has_api_key: true, api_key_hint: "sk-ant-…f3Ah",
    });
    render(<ConnectScreen captureStatus={null} />);
    expect(await screen.findByText(/sk-ant-…f3Ah/)).toBeTruthy();
    // Never render an input holding the actual secret value.
    expect(document.querySelector('input[type="password"]')).toBeNull();
    expect(document.body.innerHTML).not.toMatch(/sk-ant-[^…][a-zA-Z0-9]{10,}/);
  });

  it("saving a key calls putSettings with the entered value", async () => {
    vi.mocked(api.getSettings).mockResolvedValue(baseSettings);
    render(<ConnectScreen captureStatus={null} />);
    const input = await screen.findByPlaceholderText(/sk-ant-/i);
    fireEvent.change(input, { target: { value: "sk-ant-testkey123" } });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/i }));
    await waitFor(() =>
      expect(api.putSettings).toHaveBeenCalledWith({ anthropic_api_key: "sk-ant-testkey123" }));
  });
});

describe("ConnectScreen — OpenFlight setup card", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the copy-paste config with device_id OpenFlight and the detected LAN IP", async () => {
    render(<ConnectScreen captureStatus={null} />);
    expect(await screen.findByText(/"device_id": "OpenFlight"/)).toBeTruthy();
    // LAN IP shown both inside the JSON block and prominently in the copy.
    expect(screen.getAllByText(/192\.168\.1\.50/).length).toBeGreaterThan(0);
  });
});
