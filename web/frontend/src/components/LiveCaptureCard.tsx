import { useCallback, useEffect, useState } from "react";
import {
  getCameras, startLiveCapture, stopLiveCapture, getLiveCaptureStatus,
} from "../lib/api";
import { useLiveCaptureSse } from "../lib/useLiveCaptureSse";
import type { CameraInfo, LiveCaptureStatus, LiveSwingCaptured } from "../lib/types";

/** Live swing capture — keeps a rolling buffer of the bay cameras and, on each
 *  launch-monitor shot, flushes the surrounding window to a clip and runs it through the
 *  normal swing pipeline (auto-pairing the swing to that shot). Hardware-free:
 *  with no camera connected it stays idle and reports source "none". */
export function LiveCaptureCard() {
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [deviceLeft, setDeviceLeft] = useState("0");    // down-the-line camera
  const [deviceRight, setDeviceRight] = useState("1");  // face-on camera
  const [mono, setMono] = useState(false);
  const [windowS, setWindowS] = useState("4");
  const [delayS, setDelayS] = useState("0.6");
  const [status, setStatus] = useState<LiveCaptureStatus | null>(null);
  const [recent, setRecent] = useState<LiveSwingCaptured[]>([]);

  const refresh = useCallback(() => {
    getLiveCaptureStatus().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    getCameras().then((cams) => {
      setCameras(cams);
      if (cams[0]) setDeviceLeft(String(cams[0].index));
      if (cams[1]) setDeviceRight(String(cams[1].index));
    }).catch(() => {});
  }, [refresh]);

  const running = !!status?.running;
  useLiveCaptureSse(running, {
    live_capture_status: (d: LiveCaptureStatus) => setStatus(d),
    live_swing_captured: (d: LiveSwingCaptured) =>
      setRecent((r) => [d, ...r].slice(0, 5)),
  });

  const onStart = () => {
    startLiveCapture({
      device_left: parseInt(deviceLeft || "0", 10) || 0,
      device_right: mono ? null : (parseInt(deviceRight || "1", 10) || 0),
      mono,
      window_s: parseFloat(windowS || "4") || 4,
      post_shot_delay_s: parseFloat(delayS || "0.6") || 0.6,
    }).then(setStatus).catch(() => {});
  };
  const onStop = () => { stopLiveCapture().then(setStatus).catch(() => {}); };

  const sel = "mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]";
  const opts = cameras.length ? cameras
    : [{ index: 0, name: "Camera 0" }, { index: 1, name: "Camera 1" }];
  const sourceLabel =
    status?.source === "dual" ? "two cameras"
      : status?.source === "single" ? "one camera"
        : "no camera";

  return (
    <div className="rounded-2xl bg-[#1A211D] p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-[#E7EEE9]">Live Swing Capture</h2>
        <span className={"text-xs px-2 py-0.5 rounded-full " + (running
          ? "bg-[#79BC30] text-[#0A0D0B] font-medium"
          : "bg-[#2A332C] text-[#8B978F]")}>
          {running ? "running" : "idle"}
        </span>
      </div>
      <p className="text-sm text-[#8B978F]">
        Records each swing automatically when the launch monitor reports a shot —
        no manual trigger. Needs the bay cameras mounted; with none connected it
        stays idle.
      </p>

      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs text-[#8B978F]">Down-the-line camera
          <select className={sel} value={deviceLeft} disabled={running}
                  onChange={(e) => setDeviceLeft(e.target.value)}>
            {opts.map((c) => <option key={c.index} value={c.index}>{c.name}</option>)}
          </select></label>
        <label className={"text-xs " + (mono ? "text-[#8B978F] opacity-40" : "text-[#8B978F]")}>
          Face-on camera
          <select className={sel} value={deviceRight} disabled={mono || running}
                  onChange={(e) => setDeviceRight(e.target.value)}>
            {opts.map((c) => <option key={c.index} value={c.index}>{c.name}</option>)}
          </select></label>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs text-[#8B978F]">Buffer window (s)
          <input className={sel} value={windowS} disabled={running}
                 onChange={(e) => setWindowS(e.target.value)} /></label>
        <label className="text-xs text-[#8B978F]">Post-shot delay (s)
          <input className={sel} value={delayS} disabled={running}
                 onChange={(e) => setDelayS(e.target.value)} /></label>
      </div>

      <label className="flex items-center gap-2 text-xs text-[#8B978F]">
        <input type="checkbox" checked={mono} disabled={running}
               onChange={(e) => setMono(e.target.checked)} />
        Single-camera test mode (one webcam — validates capture only; full analysis
        needs both bay cameras)
      </label>

      <div className="flex items-center gap-4">
        {!running
          ? <button onClick={onStart}
              className="px-4 py-2 rounded-lg bg-[#79BC30] text-[#0A0D0B] font-medium">Start Capture</button>
          : <button onClick={onStop}
              className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9]">Stop</button>}
        {status && (
          <span className="text-xs text-[#8B978F]">
            {sourceLabel}
            <span className="mx-1">·</span>{status.buffered_frames} frames buffered
            <span className="mx-1">·</span>{status.swing_count} captured
          </span>
        )}
      </div>

      {status?.last_error && (
        <p className="text-xs text-red-400">{status.last_error}</p>
      )}

      {recent.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-sm font-medium text-[#8B978F]">Recently captured</h3>
          <ul className="space-y-1">
            {recent.map((s, i) => (
              <li key={`${s.swing_id}-${i}`}
                  className="rounded-lg bg-[#0A0D0B] px-3 py-2 text-xs text-[#E7EEE9]">
                Swing #{s.swing_id}
                {s.shot_id != null && (
                  <><span className="mx-1 text-[#8B978F]">·</span>paired to shot #{s.shot_id}</>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
