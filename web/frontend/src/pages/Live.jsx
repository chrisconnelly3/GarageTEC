import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getSwing, mediaUrl } from "../api";
import MetricCard from "../components/MetricCard";

// Body-movement metric names get top billing; ball/club go to the compact strip.
const BODY_METRICS = new Set([
  "shoulder_tilt_deg", "hip_sway_in", "spine_angle_deg", "early_extension_in",
  "hand_depth_in", "shoulder_turn_deg", "hip_turn_deg",
]);

export default function Live({ lastSwing }) {
  const [detail, setDetail] = useState(null);
  const [slowmo, setSlowmo] = useState(false);
  const [skeleton, setSkeleton] = useState(true);

  useEffect(() => {
    if (lastSwing?.swing_id) getSwing(lastSwing.swing_id).then(setDetail);
  }, [lastSwing]);

  if (!detail) {
    return <main><h1>Waiting for R50… take a shot</h1></main>;
  }

  const { swing, metrics, shot, coaching, media } = detail;
  const annotated = media.find((m) => m.kind === "annotated_video");
  const raw = media.find((m) => m.kind === "source_video") || annotated;
  const video = skeleton ? annotated || raw : raw;
  const read = coaching[0]?.content || {};
  const body = metrics.filter((m) => BODY_METRICS.has(m.name));

  return (
    <main className="live">
      {/* HERO — replay */}
      <section className="hero">
        <h1>Last swing · {swing.club || "—"}{" "}
          <Link to={`/swing/${swing.id}`}>review →</Link></h1>
        {video && (
          <video key={video.path} src={mediaUrl(video.path)} controls
                 width={720}
                 ref={(el) => { if (el) el.playbackRate = slowmo ? 0.25 : 1.0; }} />
        )}
        <div className="hero-controls">
          <button onClick={() => setSlowmo((s) => !s)}>
            {slowmo ? "Realtime" : "Slow-mo"}
          </button>
          <button onClick={() => setSkeleton((s) => !s)}>
            {skeleton ? "Hide skeleton" : "Show skeleton"}
          </button>
        </div>
      </section>

      {/* PRIMARY — body metrics */}
      <section className="body-metrics">
        <h2>Body</h2>
        <div className="cards">
          {body.map((m) => (
            <MetricCard key={m.id} name={m.name} value={m.value} unit={m.unit}
                        lowConfidence={m.method === "estimate"} />
          ))}
        </div>
      </section>

      {/* PRIMARY — AI read */}
      <section className="ai-read">
        <h2>{read.headline || "AI read"}</h2>
        <ul>{(read.findings || []).map((f, i) => <li key={i}>{f}</li>)}</ul>
        {read.drills?.length > 0 && (
          <>
            <h3>Drill</h3>
            <ul>{read.drills.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </>
        )}
      </section>

      {/* SECONDARY — compact ball/club strip */}
      {shot && (
        <section className="ball-club-strip">
          <span>Ball {shot.ball_speed} mph</span>
          <span>Spin {shot.total_spin}</span>
          <span>Launch {shot.vla}°</span>
          <span>Carry {shot.carry}</span>
          {shot.club_speed != null && <span>Club {shot.club_speed} mph</span>}
          {shot.club_path != null && <span>Path {shot.club_path}°</span>}
          {shot.face_to_target != null && <span>Face {shot.face_to_target}°</span>}
          {shot.attack_angle != null && <span>AoA {shot.attack_angle}°</span>}
        </section>
      )}
    </main>
  );
}
