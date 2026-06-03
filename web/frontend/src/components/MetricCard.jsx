function delta(label, v) {
  if (v === undefined || v === null) return null;
  const sign = v > 0 ? "+" : "";
  return (
    <div className="delta">
      {label}: {sign}
      {v}
    </div>
  );
}

export default function MetricCard({
  name,
  value,
  unit,
  vsBaseline,
  vsIdeal,
  lowConfidence,
}) {
  return (
    <div className="card">
      <div className="card-name">{name}</div>
      <div className="card-value">
        {value} {unit}
      </div>
      {delta("vs baseline", vsBaseline)}
      {delta("vs ideal", vsIdeal)}
      {lowConfidence && <div className="flag">low confidence</div>}
    </div>
  );
}
