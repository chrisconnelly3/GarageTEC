// web/frontend/src/components/CalibrationCard.tsx
import { useEffect, useState, useCallback, useRef } from "react";
import {
  startCalibration, stopCalibration, runCalibration, getCameras,
  getActiveCalibration, getCalibrationHistory, activateCalibration,
} from "../lib/api";
import { useCalibrationSse } from "../lib/useCalibrationSse";
import type {
  CalibrationResult, ActiveCalibration, CalibrationHistoryItem, CameraInfo,
} from "../lib/types";

// Defaults until the backend status reports its targets (varied-angle poses).
const DEFAULT_TARGET = 24;
const DEFAULT_MIN = 15;

export function CalibrationCard() {
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [deviceLeft, setDeviceLeft] = useState("0");    // down-the-line camera
  const [deviceRight, setDeviceRight] = useState("1");  // face-on camera
  const [cols, setCols] = useState("9");
  const [rows, setRows] = useState("6");
  const [squareIn, setSquareIn] = useState("1.0");      // inches; converted to mm
  const [mono, setMono] = useState(false);              // single-camera test mode
  const [capturing, setCapturing] = useState(false);
  const [goodPoses, setGoodPoses] = useState(0);
  const [coverage, setCoverage] = useState<[number, number][]>([]);
  const [tiltBuckets, setTiltBuckets] = useState(0);
  const [target, setTarget] = useState(DEFAULT_TARGET);
  const [minPoses, setMinPoses] = useState(DEFAULT_MIN);
  const [result, setResult] = useState<CalibrationResult | null>(null);
  const [active, setActive] = useState<ActiveCalibration | null>(null);
  const [history, setHistory] = useState<CalibrationHistoryItem[]>([]);
  const autoRan = useRef(false);            // fire auto-run at target once

  const refreshActive = useCallback(() => {
    getActiveCalibration().then(setActive).catch(() => {});
  }, []);

  const refreshHistory = useCallback(() => {
    getCalibrationHistory().then(setHistory).catch(() => {});
  }, []);

  useEffect(() => {
    refreshActive();
    refreshHistory();
    getCameras().then((cams) => {
      setCameras(cams);
      if (cams[0]) setDeviceLeft(String(cams[0].index));
      if (cams[1]) setDeviceRight(String(cams[1].index));
    }).catch(() => {});
  }, [refreshActive, refreshHistory]);

  // Run calibration, then stop capturing (used by both the button and auto-run).
  const runAndStop = useCallback(() => {
    runCalibration().then(setResult).catch(() => {})
      .finally(() => { stopCalibration().finally(() => setCapturing(false)); });
  }, []);

  useCalibrationSse(capturing, {
    calibration_status: (d) => {
      setGoodPoses(d.good_poses);
      setCoverage(d.coverage);
      setTiltBuckets(d.tilt_buckets ?? 0);
      if (d.target_poses) setTarget(d.target_poses);
      if (d.min_poses) setMinPoses(d.min_poses);
      // Auto-proceed to Run once enough varied poses collected (one-shot).
      if (!autoRan.current && d.good_poses >= (d.target_poses ?? DEFAULT_TARGET)) {
        autoRan.current = true;
        runAndStop();
      }
    },
    calibration_done: () => { refreshActive(); refreshHistory(); },
  });

  const onStart = () => {
    autoRan.current = false;
    setResult(null);
    startCalibration({
      device_left: parseInt(deviceLeft || "0", 10) || 0,
      device_right: mono ? null : (parseInt(deviceRight || "1", 10) || 0),
      cols: parseInt(cols || "9", 10) || 9,
      rows: parseInt(rows || "6", 10) || 6,
      square_mm: (parseFloat(squareIn || "1") || 1) * 25.4,
      mono,
    }).then(() => setCapturing(true)).catch(() => {});
  };
  const onStop = () => { stopCalibration().finally(() => setCapturing(false)); };
  const onRun = () => { runAndStop(); };

  const onActivate = (id: number) => {
    activateCalibration(id)
      .then(() => { refreshActive(); refreshHistory(); })
      .catch(() => {});
  };

  const covered = new Set(coverage.map(([c, r]) => `${c},${r}`));
  const grid = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++)
    grid.push(<div key={`${c},${r}`} className={
      "h-6 rounded " + (covered.has(`${c},${r}`) ? "bg-[#79BC30]" : "bg-[#1A211D]")} />);

  return (
    <div className="rounded-2xl bg-[#1A211D] p-6 space-y-4">
      <h2 className="text-xl font-semibold text-[#E7EEE9]">Camera Calibration</h2>
      <p className="text-sm text-[#8B978F]">
        Recalibrate the bay cameras if they've been moved. See the calibration guide
        for the checkerboard. Square size is in inches (converted automatically).
      </p>

      {(() => {
        const opts = cameras.length ? cameras
          : [{ index: 0, name: "Camera 0" }, { index: 1, name: "Camera 1" }];
        const sel = "mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]";
        return (
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs text-[#8B978F]">Down-the-line camera
              <select className={sel} value={deviceLeft}
                      onChange={(e) => setDeviceLeft(e.target.value)}>
                {opts.map((c) => <option key={c.index} value={c.index}>{c.name}</option>)}
              </select></label>
            <label className={"text-xs " + (mono ? "text-[#8B978F] opacity-40" : "text-[#8B978F]")}>
              Face-on camera
              <select className={sel} value={deviceRight} disabled={mono}
                      onChange={(e) => setDeviceRight(e.target.value)}>
                {opts.map((c) => <option key={c.index} value={c.index}>{c.name}</option>)}
              </select></label>
          </div>
        );
      })()}

      <div className="grid grid-cols-3 gap-3">
        <label className="text-xs text-[#8B978F]">Inner cols
          <input className="mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]"
                 value={cols} onChange={(e) => setCols(e.target.value)} /></label>
        <label className="text-xs text-[#8B978F]">Inner rows
          <input className="mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]"
                 value={rows} onChange={(e) => setRows(e.target.value)} /></label>
        <label className="text-xs text-[#8B978F]">Square (in)
          <input className="mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]"
                 value={squareIn} onChange={(e) => setSquareIn(e.target.value)} /></label>
      </div>

      <label className="flex items-center gap-2 text-xs text-[#8B978F]">
        <input type="checkbox" checked={mono}
               onChange={(e) => setMono(e.target.checked)} />
        Single-camera test mode (laptop webcam — validates capture/detection only;
        real calibration needs the two bay cameras)
      </label>

      {capturing && (
        <img alt="calibration preview" src="/api/calibration/preview"
             className="w-full rounded-lg border border-[#2A332C]" />
      )}

      <div className="flex items-center gap-4">
        <div className="grid grid-cols-4 gap-1 flex-1">{grid}</div>
        <div className="text-right whitespace-nowrap">
          <div className="text-[#E7EEE9] text-sm">
            {goodPoses} / {target} good poses
          </div>
          <div className="text-[10px] text-[#8B978F]">
            {tiltBuckets} tilt angle{tiltBuckets === 1 ? "" : "s"}
            {capturing ? " · auto-runs at target" : ""}
          </div>
        </div>
      </div>
      {capturing && (
        <p className="text-[11px] text-[#8B978F]">
          Move the board around AND tilt it at different angles (flat, tilted
          left/right, near/far) — only new positions &amp; angles count.
        </p>
      )}

      <div className="flex gap-3">
        {!capturing
          ? <button onClick={onStart}
              className="px-4 py-2 rounded-lg bg-[#79BC30] text-[#0A0D0B] font-medium">Start Capture</button>
          : <button onClick={onStop}
              className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9]">Stop</button>}
        <button onClick={onRun} disabled={goodPoses < minPoses}
          className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9] disabled:opacity-40">
          Run Calibration</button>
        <a href="/api/calibration/export"
          className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9]">Export</a>
      </div>

      {result && (
        <div className={"text-sm " + (result.ok ? "text-[#79BC30]" : "text-red-400")}>
          {result.ok
            ? `✓ Calibrated · ${result.n_poses} poses · reproj ${result.reprojection_error?.toFixed(2)}px`
            : `✗ ${result.error}`}
        </div>
      )}
      {active && (
        <div className="text-xs text-[#8B978F]">
          Active: #{active.id} · {active.n_poses} poses · {active.reprojection_error.toFixed(2)}px · {active.created_at}
        </div>
      )}

      {/* History list */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-[#8B978F]">History</h3>
        {history.length === 0 ? (
          <p className="text-xs text-[#8B978F] opacity-60">No calibrations yet.</p>
        ) : (
          <ul className="space-y-1">
            {history.map((item) => (
              <li key={item.id}
                  className="flex items-center justify-between rounded-lg bg-[#0A0D0B] px-3 py-2 text-xs">
                <span className="text-[#E7EEE9]">
                  #{item.id}
                  <span className="mx-1 text-[#8B978F]">·</span>
                  {item.created_at.slice(0, 16).replace("T", " ")}
                  <span className="mx-1 text-[#8B978F]">·</span>
                  {item.n_poses} poses
                  <span className="mx-1 text-[#8B978F]">·</span>
                  {item.reprojection_error.toFixed(2)}px
                </span>
                <span className="flex items-center gap-2">
                  {item.is_active ? (
                    <span className="rounded px-2 py-0.5 bg-[#79BC30] text-[#0A0D0B] font-medium">active</span>
                  ) : (
                    <button
                      onClick={() => onActivate(item.id)}
                      className="rounded px-2 py-0.5 bg-[#2A332C] text-[#E7EEE9] hover:bg-[#3A4A3C]">
                      Activate
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
