export type Handedness = "R" | "L";
export type CaptureState = "stopped" | "listening" | "connected" | "paused";

export interface Player { id: number; name: string; height_in: number; handedness: Handedness; created_at: string; }
export interface Session { id: number; player_id: number; started_at: string; ended_at: string | null; location: string | null; notes: string | null; }
export interface Swing { id: number; session_id: number; player_id: number; created_at: string; source_video_path: string | null; view_layout: string | null; fps: number | null; width: number | null; height: number | null; club: string | null; notes: string | null; shot_id: number | null; }
export interface Metric { id: number; swing_id: number; name: string; context: string | null; value: number | null; unit: string | null; method: string | null; created_at: string; }
export interface Moment { id: number; swing_id: number; kind: string; view: string | null; frame_index: number | null; time_s: number | null; }
export interface Media { id: number; swing_id: number; kind: string; path: string; meta: unknown | null; }
export interface Shot { id: number; swing_id: number | null; player_id: number | null; session_id: number | null; captured_at: string; device_id: string | null; shot_number: number | null; ball_speed: number | null; total_spin: number | null; spin_axis: number | null; hla: number | null; vla: number | null; carry: number | null; club_speed: number | null; attack_angle: number | null; club_path: number | null; face_to_target: number | null; }

export interface CoachFinding { metric: string; context?: string | null; value: number; unit?: string | null; vs_baseline?: string | null; vs_ideal?: string | null; ball_effect?: string | null; severity?: "good" | "neutral" | "bad" | null; }
export interface CoachDrill { name: string; why?: string | null; how?: string | null; }
export interface CoachContent { headline: string; findings: CoachFinding[]; drills: CoachDrill[]; confidence_notes?: string[]; }
export interface Coaching { id: number; swing_id: number | null; session_id: number | null; kind: string; content: CoachContent | null; model: string | null; created_at: string; }

export interface SwingDetail { swing: Swing; metrics: Metric[]; moments: Moment[]; shot: Shot | null; coaching: Coaching[]; media: Media[]; }
export interface SessionDetail { session: Session; swings: Swing[]; coaching: Coaching[]; }
export interface CaptureStatus { status: CaptureState; paused: boolean; connected: boolean; shot_count: number; active_player_id: number | null; last_error: string | null; }
export interface HistoryPoint { swing_id: number; created_at: string; value: number; }
export interface History { player: number; metric: string; context: string; points: HistoryPoint[]; }
export interface SyncProposal { swing_id: number; shot_id: number; confidence: number; reason: string; }
export interface SyncProposals { session: number; proposals: SyncProposal[]; unmatched_swings: Swing[]; unmatched_shots: Shot[]; }
export interface ActivePlayerIn { name: string; height_in: number; handedness: Handedness; }
