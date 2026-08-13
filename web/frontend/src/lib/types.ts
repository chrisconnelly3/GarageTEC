export type Handedness = "R" | "L";
export type CaptureState = "stopped" | "listening" | "connected" | "paused";

export interface Player { id: number; name: string; height_in: number; handedness: Handedness; created_at: string; }
export interface Session { id: number; player_id: number; started_at: string; ended_at: string | null; location: string | null; notes: string | null; }
export interface Swing { id: number; session_id: number; player_id: number; created_at: string; source_video_path: string | null; view_layout: string | null; fps: number | null; width: number | null; height: number | null; club: string | null; notes: string | null; shot_id: number | null; }
export interface Metric { id: number; swing_id: number; name: string; context: string | null; value: number | null; unit: string | null; method: string | null; created_at: string; }
export interface Moment { id: number; swing_id: number; kind: string; view: string | null; frame_index: number | null; time_s: number | null; }
export interface Media { id: number; swing_id: number; kind: string; path: string; meta: unknown | null; }
export interface Shot { id: number; swing_id: number | null; player_id: number | null; session_id: number | null; captured_at: string; device_id: string | null; shot_number: number | null; ball_speed: number | null; total_spin: number | null; spin_axis: number | null; hla: number | null; vla: number | null; carry: number | null; club_speed: number | null; attack_angle: number | null; club_path: number | null; face_to_target: number | null; club: string | null; }
export type MetricZone = "green" | "yellow" | "red";
export type MetricState = "ok" | "needs_3d" | "raw";
export type MetricDirection = "match" | "higher" | "lower" | "range";

export interface BallBenchmark {
  key: string; label: string; unit: string; value: number; target: number;
  delta: number; near: boolean;
  direction: MetricDirection | null;
  zone: MetricZone | null;
}
// Raw R50/GSPro fields we surface but don't benchmark (no TrackMan column): club
// path, face-to-target, spin axis, back/side spin. value may be null.
export interface BallRawField { key: string; label: string; unit: string; value: number | null; }

export interface CoachFinding { metric: string; context?: string | null; value: number; unit?: string | null; vs_baseline?: string | null; vs_ideal?: string | null; ball_effect?: string | null; severity?: "good" | "neutral" | "bad" | null; }
export interface CoachDrill { name: string; why?: string | null; how?: string | null; }
export interface CoachContent { headline: string; summary?: string | null; findings: CoachFinding[]; drills: CoachDrill[]; confidence_notes?: string[]; }
export interface Coaching { id: number; swing_id: number | null; session_id: number | null; kind: string; content: CoachContent | null; model: string | null; created_at: string; }

export interface Benchmark {
  name: string; context: string; value: number; unit: string | null;
  target: number | null; delta: number | null; comparable: boolean;
  reason: string | null;
  direction: MetricDirection | null;
  zone: MetricZone | null;
  state: MetricState;
}
export type TrustTier = "measured" | "estimated" | "absent";
export type TrustMap = Record<string, TrustTier>;
export interface SwingDetail { swing: Swing; metrics: Metric[]; benchmarks?: Benchmark[]; ball_benchmarks?: BallBenchmark[]; ball_raw?: BallRawField[]; moments: Moment[]; shot: Shot | null; coaching: Coaching[]; media: Media[]; trust?: TrustMap; }
export interface SessionDetail { session: Session; swings: Swing[]; coaching: Coaching[]; }
export interface CaptureStatus { status: CaptureState; paused: boolean; connected: boolean; shot_count: number; active_player_id: number | null; active_club: string | null; last_error: string | null; session_active: boolean; active_session_id: number | null; enrichment_status: string; openflight_host: string | null; }
export interface HistoryPoint { swing_id: number; created_at: string; value: number; }
export interface History { player: number; metric: string; context: string; target: number | null; points: HistoryPoint[]; }
export interface BallHistoryPoint { shot_id: number; captured_at: string; value: number; }
// Ball-metric trend vs the TrackMan tour average for the selected club. `target`
// is null when no club is given or the (metric,club) has no tour average.
export interface BallHistory {
  player: number; metric: string; club: string | null;
  target: number | null; points: BallHistoryPoint[];
}
export interface SessionStats {
  session_id: number;
  swing_count: number;
  club_counts: Record<string, number>;
  top_ball: { label: string; value: number; unit: string } | null;
  tour_range: { in_range: number; total: number } | null;
  latest_swing_id: number | null;
  takeaway: string | null;
}
export interface ActivePlayerIn { name: string; height_in: number; handedness: Handedness; }
export interface Settings {
  idle_minutes: number; units: "yards" | "meters"; port: number;
  has_api_key: boolean; api_key_hint: string;
  anthropic_api_key?: string; // write-only: accepted by PUT, never returned by GET
}
export interface OpenFlightConnector {
  connectors: { type: string; enabled: boolean; host: string; port: number; device_id: string }[];
}
export interface SetupInfo { lan_ip: string; port: number; openflight_connector: OpenFlightConnector; }
export interface PlayerWithCounts extends Player { swing_count: number; session_count: number; }
export interface SwingSummary {
  id: number; created_at: string; club: string | null; has_shot: boolean;
  hip_sway_in: number | null; shoulder_tilt_deg: number | null;
}

export interface CameraInfo { index: number; name: string; }
export interface CalibrationStartIn {
  device_left: number;             // down-the-line camera
  device_right?: number | null;    // face-on camera (null in mono test mode)
  cols: number; rows: number; square_mm: number;
  mono?: boolean;                  // single-camera (laptop webcam) test mode
}
export interface CalibrationStatus {
  capturing: boolean; good_poses: number; coverage: [number, number][];
  tilt_buckets: number; min_poses: number; target_poses: number; max_poses: number;
  device_left: number; device_right: number | null; mono: boolean;
  cols: number; rows: number;
}
export interface CalibrationResult {
  ok: boolean; n_poses?: number; reprojection_error?: number; error?: string;
}
export interface ActiveCalibration {
  id: number; created_at: string; n_poses: number;
  reprojection_error: number; cols: number; rows: number; device_index: number;
}
export interface CalibrationHistoryItem {
  id: number; created_at: string; n_poses: number;
  reprojection_error: number; is_active: number;
}

// Live swing capture: a rolling frame buffer is flushed to a clip on each R50
// shot and run through the proven offline pipeline. Degrades to source:"none".
export interface LiveCaptureStartIn {
  device_left?: number;
  device_right?: number | null;   // null / mono => single camera
  mono?: boolean;
  fps?: number | null;
  window_s?: number | null;        // rolling buffer seconds
  post_shot_delay_s?: number | null;
}
export interface LiveCaptureStatus {
  running: boolean; capturing: boolean;
  source: "none" | "single" | "dual";
  buffered_frames: number; swing_count: number;
  fps: number; window_s: number; post_shot_delay_s: number;
  last_error: string | null;
}
export interface LiveSwingCaptured {
  swing_id: number; shot_id: number | null;
  player_id: number | null; session_id: number | null;
}
