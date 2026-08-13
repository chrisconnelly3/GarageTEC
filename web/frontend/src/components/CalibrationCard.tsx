// web/frontend/src/components/CalibrationCard.tsx
import { useEffect, useState, useCallback, useRef } from "react";
import { Printer } from "lucide-react";
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

/** Start/Recalibrate button that shows it is working. Opening two USB cameras
 *  takes several seconds and produces no output of its own, so without a busy
 *  state the button reads as broken and users tap it repeatedly. */
function StartButton({ onClick, starting, label }: {
  onClick: () => void; starting: boolean; label: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={starting}
      aria-busy={starting}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-garage-green
                 text-[#0A0D0B] font-medium min-h-[44px] disabled:opacity-70
                 disabled:cursor-wait"
    >
      {starting && (
        <span
          aria-hidden="true"
          className="w-4 h-4 rounded-full border-2 border-[#0A0D0B]/30
                     border-t-[#0A0D0B] animate-spin"
        />
      )}
      {starting ? "Starting cameras…" : label}
    </button>
  );
}

export function CalibrationCard() {
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [deviceLeft, setDeviceLeft] = useState("0");    // down-the-line camera
  const [deviceRight, setDeviceRight] = useState("1");  // face-on camera
  const [cols, setCols] = useState("9");
  const [rows, setRows] = useState("6");
  // Millimetres end-to-end: the API takes square_mm, the printable board is
  // generated in mm, and mm is finer than inches for measuring a small square.
  // Default matches the board this app prints, so most users never touch it.
  const [squareMm, setSquareMm] = useState("25");
  const [mono, setMono] = useState(false);              // single-camera test mode
  const [capturing, setCapturing] = useState(false);
  // Opening two USB cameras takes a few seconds with no output of its own, so
  // without this the Recalibrate/Start button looks dead and users click again.
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
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
    if (starting) return;               // guard against double-taps while opening
    autoRan.current = false;
    setResult(null);
    setStartError(null);
    setStarting(true);
    startCalibration({
      device_left: parseInt(deviceLeft || "0", 10) || 0,
      device_right: mono ? null : (parseInt(deviceRight || "1", 10) || 0),
      cols: parseInt(cols || "9", 10) || 9,
      rows: parseInt(rows || "6", 10) || 6,
      square_mm: parseFloat(squareMm || "25") || 25,
      mono,
    })
      .then(() => setCapturing(true))
      .catch(() => setStartError(
        "Could not open the cameras. Check they are plugged in and not in use " +
        "by another app, then try again."))
      .finally(() => setStarting(false));
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
        Calibration teaches the app where your two bay cameras are, so it can
        turn their footage into real 3D body angles. All sizes here are in
        millimetres.
      </p>

      <details className="rounded-xl bg-[#0A0D0B] border border-[#242C27] p-4 text-sm text-[#8B978F] space-y-2">
        <summary className="cursor-pointer text-[#E7EEE9] font-medium select-none">
          How calibration works
        </summary>
        <p>
          <span className="text-[#E7EEE9]">What it is: </span>
          calibration shows both cameras a known checkerboard pattern so the
          software can work out each camera's lens fingerprint and exactly
          how far apart and at what angle the two cameras sit.
        </p>
        <p>
          <span className="text-[#E7EEE9]">What you need: </span>
          a checkerboard (9×6 inner corners) glued flat to a rigid board
          (foam board, clipboard, MDF). Use the button below to print the exact
          pattern this app expects — no need to hunt for one online.
        </p>
        <p>
          <span className="text-[#E7EEE9]">Printing it (this part matters): </span>
          set orientation to <span className="text-[#E7EEE9]">Landscape</span> —
          the board is wider than it is tall, so Portrait will shrink it to fit
          and every measurement will be wrong. Set scale to
          {' '}<span className="text-[#E7EEE9]">100% / Actual Size</span> and turn
          &quot;fit to page&quot; / &quot;shrink to fit&quot; OFF. Then measure one
          printed square with a ruler and, if it is not exactly 25&nbsp;mm, type
          the real number into
          {' '}<span className="text-[#E7EEE9]">Square size (mm)</span> below —
          printers are rarely exact, and this number is what makes your 3D
          numbers metrically correct.
        </p>
        <p>
          <span className="text-[#E7EEE9]">How to wave the board: </span>
          move it through lots of positions (center, left, right, near, far)
          and tilts (flat, tilted left/right, angled toward/away). Keep the
          whole board visible to both cameras and hold each pose still for
          about a second. Aim for 20–40 good poses.
        </p>
        <p>
          <span className="text-[#E7EEE9]">How to verify: </span>
          after calibrating, take a normal swing. A tour-quality swing should
          read roughly 89° shoulder turn and 48° hip turn at the top of the
          backswing. Numbers wildly off (10°, or 200°) mean something's
          wrong — recapture.
        </p>
        <p className="text-xs">
          Full guide:{' '}
          <code className="bg-[#1A211D] px-1.5 py-0.5 rounded">
            docs/guides/bay-camera-calibration-guide.md
          </code>
        </p>
      </details>

      {active && !capturing && (
        <div className="rounded-xl border border-[#242C27] bg-[#0A0D0B] p-4 space-y-2">
          <p className="text-sm text-[#E7EEE9]">
            Active calibration: #{active.id} · {active.n_poses} poses ·{' '}
            {active.reprojection_error.toFixed(2)}px reprojection error ·{' '}
            {active.created_at}
          </p>
          <p className="text-xs text-[#8B978F]">
            Recalibrate any time a camera gets bumped or moved — calibration
            is a measurement of where the cameras are, so it goes stale the
            moment they shift.
          </p>
          <StartButton onClick={onStart} starting={starting} label="Recalibrate" />
          {startError && (
            <p className="text-xs text-garage-red">{startError}</p>
          )}
        </div>
      )}

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
        <label className="text-xs text-[#8B978F]">Square size (mm)
          <input className="mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]"
                 value={squareMm} onChange={(e) => setSquareMm(e.target.value)} /></label>
      </div>

      {/* Ship the board rather than making users find a matching one online: a
          wrong square count or a scaled print is the most common calibration
          failure. Generated to match the inner-corner counts above. */}
      <a
        href={`/api/calibration/checkerboard.svg?cols=${
          (parseInt(cols || "9", 10) || 9) + 1}&rows=${
          (parseInt(rows || "6", 10) || 6) + 1}&square_mm=25`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border
                   border-[#242C27] bg-[#1A211D] text-[#E7EEE9] text-sm
                   min-h-[44px] w-fit"
      >
        <Printer className="w-4 h-4 text-garage-green" />
        Open printable checkerboard
      </a>

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

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1">
          <p className="text-xs font-semibold text-[#8B978F]">1. Capture poses</p>
          <p className="text-[11px] text-[#8B978F]">
            Starts recording checkerboard poses from the cameras.
          </p>
          {!capturing
            ? <StartButton onClick={onStart} starting={starting} label="Start Capture" />
            : <button onClick={onStop}
                className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9] min-h-[44px]">Stop</button>}
          {startError && !capturing && (
            <p className="text-xs text-garage-red">{startError}</p>
          )}
        </div>
        <div className="space-y-1">
          <p className="text-xs font-semibold text-[#8B978F]">2. Calculate calibration</p>
          <p className="text-[11px] text-[#8B978F]">
            Computes the result from the poses just captured (needs {minPoses}+ good poses).
          </p>
          <button onClick={onRun} disabled={goodPoses < minPoses}
            className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9] disabled:opacity-40 min-h-[44px]">
            Run Calibration</button>
        </div>
      </div>

      {result && (
        <div className={"text-sm " + (result.ok ? "text-[#79BC30]" : "text-red-400")}>
          {result.ok
            ? `✓ Calibrated · ${result.n_poses} poses · reproj ${result.reprojection_error?.toFixed(2)}px`
            : `✗ ${result.error}`}
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
