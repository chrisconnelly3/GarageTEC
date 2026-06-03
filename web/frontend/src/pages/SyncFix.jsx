import { useEffect, useState } from "react";
import { getSessions, getProposals, applyMatch, unlinkSwing } from "../api";

export default function SyncFix() {
  const [sessions, setSessions] = useState([]);
  const [session, setSession] = useState("");
  const [data, setData] = useState(null);

  useEffect(() => {
    getSessions().then((ss) => {
      setSessions(ss);
      if (ss[0]) setSession(String(ss[0].id));
    });
  }, []);

  const refresh = (sid) => getProposals(sid).then(setData);
  useEffect(() => {
    if (session) refresh(session);
  }, [session]);

  async function onApply(swing_id, shot_id) {
    await applyMatch(swing_id, shot_id);
    refresh(session);
  }
  async function onUnlink(swing_id) {
    await unlinkSwing(swing_id);
    refresh(session);
  }

  return (
    <main>
      <h1>Sync fix</h1>
      <select value={session} onChange={(e) => setSession(e.target.value)}>
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>Session {s.id}</option>
        ))}
      </select>

      <h3>Proposals</h3>
      <table>
        <thead>
          <tr><th>Swing</th><th>Shot</th><th>Confidence</th><th></th></tr>
        </thead>
        <tbody>
          {(data?.proposals || []).map((p) => (
            <tr key={`${p.swing_id}-${p.shot_id}`}>
              <td>{p.swing_id}</td><td>{p.shot_id}</td>
              <td>{p.confidence.toFixed(2)}</td>
              <td>
                <button onClick={() => onApply(p.swing_id, p.shot_id)}>
                  confirm
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Unmatched swings</h3>
      <ul>
        {(data?.unmatched_swings || []).map((s) => (
          <li key={s.id}>
            Swing {s.id}{" "}
            <button onClick={() => onUnlink(s.id)}>unlink</button>
          </li>
        ))}
      </ul>
    </main>
  );
}
