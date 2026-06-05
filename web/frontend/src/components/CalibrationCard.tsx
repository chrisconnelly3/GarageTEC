// web/frontend/src/components/CalibrationCard.tsx
import { useEffect, useState, useCallback, useRef } from "react";
import {
  startCalibration, stopCalibration, runCalibration,
  getActiveCalibration, getCalibrationHistory, activateCalibration,
} from "../lib/api";
import { useCalibrationSse } from "../lib/useCalibrationSse";
import type { CalibrationResult, ActiveCalibration, CalibrationHistoryItem } from "../lib/types";

// The coverage map is a 4x3 grid and we keep one pose per cell, so full
// coverage = 12 poses. Auto-run calibration once the grid is fully covered.
const COVERAGE_CELLS = 12;

export function CalibrationCard() {
  const [device, setDevice] = useState("0");
  const [cols, setCols] = useState("9");
  const [rows, setRows] = useState("6");
  const [squareIn, setSquareIn] = useState("1.0");      // inches; converted to mm
  const [mono, setMono] = useState(false);              // single-camera test mode
  const [capturing, setCapturing] = useState(false);
  const [goodPoses, setGoodPoses] = useState(0);
  const [coverage, setCoverage] = useState<[number, number][]>([]);
  const [result, setResult] = useState<CalibrationResult | null>(null);
  const [active, setActive] = useState<ActiveCalibration | null>(null);
  const [history, setHistory] = useState<CalibrationHistoryItem[]>([]);
  const autoRan = useRef(false);            // fire auto-run at full coverage once

  const refreshActive = useCallback(() => {
    getActiveCalibration().then(setActive).catch(() => {});
  }, []);

  const refreshHistory = useCallback(() => {
    getCalibrationHistory().then(setHistory).catch(() => {});
  }, []);

  useEffect(() => {
    refreshActive();
    refreshHistory();
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
      // Auto-proceed to Run once the coverage grid is full (one-shot).
      if (!autoRan.current && d.good_poses >= COVERAGE_CELLS) {
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
      device_index: parseInt(device || "0", 10) || 0,
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
      "h-6 rounded " + (covered.has(`${c},${r}`) ? "bg-[#84CE39]" : "bg-[#1A211D]")} />);

  return (
    <div className="rounded-2xl bg-[#1A211D] p-6 space-y-4">
      <h2 className="text-xl font-semibold text-[#E7EEE9]">Camera Calibration</h2>
      <p className="text-sm text-[#8B978F]">
        Recalibrate the bay cameras if they've been moved. See the calibration guide
        for the checkerboard. Square size is in inches (converted automatically).
      </p>

      <div className="grid grid-cols-4 gap-3">
        <label className="text-xs text-[#8B978F]">Device
          <input className="mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]"
                 value={device} onChange={(e) => setDevice(e.target.value)} /></label>
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
            {goodPoses} / {COVERAGE_CELLS} good poses
          </div>
          {capturing && (
            <div className="text-[10px] text-[#8B978F]">auto-runs when full</div>
          )}
        </div>
      </div>

      <div className="flex gap-3">
        {!capturing
          ? <button onClick={onStart}
              className="px-4 py-2 rounded-lg bg-[#84CE39] text-[#0A0D0B] font-medium">Start Capture</button>
          : <button onClick={onStop}
              className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9]">Stop</button>}
        <button onClick={onRun} disabled={goodPoses < 8}
          className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9] disabled:opacity-40">
          Run Calibration</button>
        <a href="/api/calibration/export"
          className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9]">Export</a>
      </div>

      {result && (
        <div className={"text-sm " + (result.ok ? "text-[#84CE39]" : "text-red-400")}>
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
                    <span className="rounded px-2 py-0.5 bg-[#84CE39] text-[#0A0D0B] font-medium">active</span>
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
