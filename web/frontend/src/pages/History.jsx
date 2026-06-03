import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
} from "recharts";
import { getPlayers, getHistory } from "../api";

export default function History() {
  const [players, setPlayers] = useState([]);
  const [player, setPlayer] = useState("");
  const [metric, setMetric] = useState("hip_sway_in");
  const [context, setContext] = useState("impact");
  const [points, setPoints] = useState([]);

  useEffect(() => {
    getPlayers().then((ps) => {
      setPlayers(ps);
      if (ps[0]) setPlayer(String(ps[0].id));
    });
  }, []);

  useEffect(() => {
    if (player) getHistory(player, metric, context).then((d) => setPoints(d.points));
  }, [player, metric, context]);

  return (
    <main>
      <h1>History</h1>
      <div>
        <select value={player} onChange={(e) => setPlayer(e.target.value)}>
          {players.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <input value={metric} onChange={(e) => setMetric(e.target.value)} />
        <input value={context} onChange={(e) => setContext(e.target.value)} />
      </div>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="created_at" hide />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#7fb4ff" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </main>
  );
}
