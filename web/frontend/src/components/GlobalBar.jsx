export default function GlobalBar({ players, status, onSelectPlayer,
                                    onPause, onResume }) {
  const paused = status?.paused;
  const activeId = status?.active_player_id;
  const chip = paused
    ? "Paused — not recording"
    : status?.status === "connected"
      ? `Connected · ${status?.shot_count ?? 0} shots`
      : status?.status === "listening"
        ? "Waiting for R50…"
        : status?.status || "—";

  return (
    <header className="global-bar">
      <div className="players">
        {players.map((p) => (
          <button key={p.id}
            className={p.id === activeId ? "player active" : "player"}
            onClick={() => onSelectPlayer(p)}>
            {p.name}
          </button>
        ))}
      </div>
      <div className="status-chip">{chip}</div>
      {paused
        ? <button onClick={onResume}>Resume</button>
        : <button onClick={onPause}>Pause</button>}
    </header>
  );
}
