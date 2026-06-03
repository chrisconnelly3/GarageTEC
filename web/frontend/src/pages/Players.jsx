import { useEffect, useState } from "react";
import { getPlayers, createPlayer } from "../api";

export default function Players() {
  const [players, setPlayers] = useState([]);
  const [name, setName] = useState("");
  const [heightIn, setHeightIn] = useState("70");
  const [handedness, setHandedness] = useState("R");

  const load = () => getPlayers().then(setPlayers);
  useEffect(() => {
    load();
  }, []);

  async function onAdd(e) {
    e.preventDefault();
    if (!name) return;
    await createPlayer({
      name,
      height_in: parseFloat(heightIn),
      handedness,
    });
    setName("");
    load();
  }

  return (
    <main>
      <h1>Players</h1>
      <ul>
        {players.map((p) => (
          <li key={p.id}>
            {p.name} · {p.height_in}in · {p.handedness}
          </li>
        ))}
      </ul>
      <form onSubmit={onAdd}>
        <input
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          placeholder="Height (in)"
          value={heightIn}
          onChange={(e) => setHeightIn(e.target.value)}
        />
        <select value={handedness} onChange={(e) => setHandedness(e.target.value)}>
          <option value="R">R</option>
          <option value="L">L</option>
        </select>
        <button type="submit">Add player</button>
      </form>
    </main>
  );
}
