import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import useEvents from "../useEvents";
import { getSwing, mediaUrl } from "../api";
import MetricCard from "../components/MetricCard";

export default function Live() {
  const lastSwing = useEvents();
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    if (lastSwing?.swing_id) getSwing(lastSwing.swing_id).then(setDetail);
  }, [lastSwing]);

  if (!detail) return <main><h1>Waiting for the next swing…</h1></main>;

  const { swing, metrics, shot, coaching, media } = detail;
  const video = media.find((m) => m.kind === "annotated_video");
  const read = coaching[0]?.content || {};

  return (
    <main>
      <h1>
        Last swing · {swing.club || "—"}{" "}
        <Link to={`/swing/${swing.id}`}>review →</Link>
      </h1>
      {video && (
        <video src={mediaUrl(video.path)} controls width={640} />
      )}
      {read.headline && <h2>{read.headline}</h2>}
      <div className="cards">
        {metrics.map((m) => (
          <MetricCard
            key={m.id}
            name={m.name}
            value={m.value}
            unit={m.unit}
            lowConfidence={m.method === "estimate"}
          />
        ))}
      </div>
      {shot && (
        <p>
          Ball {shot.ball_speed} mph · carry {shot.carry} · VLA {shot.vla}
        </p>
      )}
      {read.drills?.length > 0 && (
        <>
          <h3>Drills</h3>
          <ul>{read.drills.map((d, i) => <li key={i}>{d}</li>)}</ul>
        </>
      )}
    </main>
  );
}
