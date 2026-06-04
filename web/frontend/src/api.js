async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

export const getPlayers = () => getJSON("/api/players");
export const createPlayer = (p) => postJSON("/api/players", p);
export const getSessions = (player) =>
  getJSON("/api/sessions" + (player ? `?player=${player}` : ""));
export const getSession = (id) => getJSON(`/api/sessions/${id}`);
export const getSwing = (id) => getJSON(`/api/swings/${id}`);
export const getHistory = (player, metric, context = "overall") =>
  getJSON(
    `/api/history?player=${player}&metric=${encodeURIComponent(
      metric
    )}&context=${encodeURIComponent(context)}`
  );
export const getProposals = (session) =>
  getJSON(`/api/sync/proposals?session=${session}`);
export const applyMatch = (swing_id, shot_id) =>
  postJSON("/api/sync/apply", { swing_id, shot_id });
export const unlinkSwing = (swing_id) =>
  postJSON("/api/sync/unlink", { swing_id });
export const mediaUrl = (path) => `/media/${path}`;

export const getCaptureStatus = () => getJSON("/api/capture/status");
export const pauseCapture = () => postJSON("/api/capture/pause", {});
export const resumeCapture = () => postJSON("/api/capture/resume", {});
export const restartCapture = () => postJSON("/api/capture/restart", {});
export const setActivePlayer = (p) => postJSON("/api/capture/active-player", p);
