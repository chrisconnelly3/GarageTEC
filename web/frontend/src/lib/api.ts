import type {
  Player, Session, SwingDetail, SessionDetail, History, SyncProposals,
  CaptureStatus, ActivePlayerIn, Settings, PlayerWithCounts, SwingSummary,
  CalibrationStartIn, CalibrationStatus, CalibrationResult, ActiveCalibration,
} from "./types";

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  if (r.status === 204) return null as T;
  return r.json() as Promise<T>;
}
async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json() as Promise<T>;
}
async function putJSON<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json() as Promise<T>;
}

export const getPlayers = () => getJSON<PlayerWithCounts[]>("/api/players");
export const createPlayer = (p: ActivePlayerIn) => postJSON<Player>("/api/players", p);

export const getSessions = (player?: number) =>
  getJSON<Session[]>("/api/sessions" + (player ? `?player=${player}` : ""));
export const getSession = (id: number) => getJSON<SessionDetail>(`/api/sessions/${id}`);

export const getSwing = (id: number) => getJSON<SwingDetail>(`/api/swings/${id}`);
export const getLatestSwing = (player: number, session?: number) =>
  getJSON<SwingDetail | null>(
    `/api/swings/latest?player=${player}` + (session ? `&session=${session}` : ""));

export const buildHistoryUrl = (player: number, metric: string, context = "impact") =>
  `/api/history?player=${player}&metric=${encodeURIComponent(metric)}&context=${encodeURIComponent(context)}`;
export const getHistory = (player: number, metric: string, context = "impact") =>
  getJSON<History>(buildHistoryUrl(player, metric, context));

export const getProposals = (session: number) =>
  getJSON<SyncProposals>(`/api/sync/proposals?session=${session}`);
export const applyMatch = (swing_id: number, shot_id: number) =>
  postJSON<{ ok: true }>("/api/sync/apply", { swing_id, shot_id });
export const unlinkSwing = (swing_id: number) =>
  postJSON<{ ok: true }>("/api/sync/unlink", { swing_id });

export const mediaUrl = (path: string) => `/media/${path}`;

export const getCaptureStatus = () => getJSON<CaptureStatus>("/api/capture/status");
export const pauseCapture = () => postJSON<CaptureStatus>("/api/capture/pause", {});
export const resumeCapture = () => postJSON<CaptureStatus>("/api/capture/resume", {});
export const restartCapture = () => postJSON<CaptureStatus & { ok: true }>("/api/capture/restart", {});
export const setActivePlayer = (p: ActivePlayerIn) =>
  postJSON<CaptureStatus>("/api/capture/active-player", p);

export const getSettings = () => getJSON<Settings>("/api/settings");
export const putSettings = (s: Partial<Settings>) => putJSON<Settings>("/api/settings", s);

export const getSwings = (player?: number, session?: number, limit = 50) => {
  const qs = new URLSearchParams();
  if (player) qs.set("player", String(player));
  if (session) qs.set("session", String(session));
  qs.set("limit", String(limit));
  return getJSON<SwingSummary[]>(`/api/swings?${qs.toString()}`);
};

export const startCalibration = (b: CalibrationStartIn) =>
  postJSON<{ ok: boolean }>("/api/calibration/start", b);
export const stopCalibration = () => postJSON<{ ok: boolean }>("/api/calibration/stop", {});
export const runCalibration = () => postJSON<CalibrationResult>("/api/calibration/run", {});
export const getCalibrationStatus = () =>
  getJSON<CalibrationStatus>("/api/calibration/status");
export const getActiveCalibration = () =>
  getJSON<ActiveCalibration | null>("/api/calibration/active");
