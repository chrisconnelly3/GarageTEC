import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getSession } from "../api";

export default function Session() {
  const { id } = useParams();
  const [data, setData] = useState(null);

  useEffect(() => {
    getSession(id).then(setData);
  }, [id]);

  if (!data) return <main><p>Loading session…</p></main>;
  const { session, swings, coaching } = data;
  const summary = coaching.find((c) => c.kind === "session")?.content;

  return (
    <main>
      <h1>Session #{session.id} · {session.location || "—"}</h1>
      {summary?.headline && <p>{summary.headline}</p>}
      <h3>Swings ({swings.length})</h3>
      <table>
        <thead><tr><th>#</th><th>Club</th><th>Matched</th><th></th></tr></thead>
        <tbody>
          {swings.map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td><td>{s.club || "—"}</td>
              <td>{s.shot_id ? "yes" : "no"}</td>
              <td><Link to={`/swing/${s.id}`}>review</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
