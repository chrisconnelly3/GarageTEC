import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getSwing, mediaUrl } from "../api";

export default function SwingReview() {
  const { id } = useParams();
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    getSwing(id).then(setDetail);
  }, [id]);

  if (!detail) return <main><p>Loading swing…</p></main>;
  const { swing, metrics, moments, shot, coaching, media } = detail;
  const video = media.find((m) => m.kind === "annotated_video");
  const read = coaching[0]?.content || {};

  return (
    <main>
      <h1>Swing #{swing.id} · {swing.club || "—"}</h1>
      {video && <video src={mediaUrl(video.path)} controls width={720} />}

      <h3>Phases</h3>
      <ol>
        {moments.map((m) => (
          <li key={m.id}>
            {m.kind} — frame {m.frame_index} ({m.time_s}s)
          </li>
        ))}
      </ol>

      <h3>Metrics</h3>
      <table>
        <thead>
          <tr><th>Metric</th><th>Context</th><th>Value</th><th>Method</th></tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.id}>
              <td>{m.name}</td><td>{m.context}</td>
              <td>{m.value} {m.unit}</td><td>{m.method}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {shot && (
        <>
          <h3>Matched shot</h3>
          <p>
            Ball {shot.ball_speed} · spin {shot.total_spin} · carry {shot.carry}
          </p>
        </>
      )}

      {read.headline && (
        <>
          <h3>Coach</h3>
          <p>{read.headline}</p>
          <ul>{(read.findings || []).map((f, i) => <li key={i}>{f}</li>)}</ul>
        </>
      )}
    </main>
  );
}
