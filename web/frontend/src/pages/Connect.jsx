import useCapture from "../useCapture";

export default function Connect({ lastCapture }) {
  const cap = useCapture(lastCapture);
  const st = cap.status;
  const connected = st?.status === "connected";

  return (
    <main className="connect">
      <h1>Connect your R50</h1>
      <p className="status">
        {connected ? "Connected to your R50"
          : st?.status === "listening" ? "Waiting for your R50…"
          : st?.last_error ? `Problem: ${st.last_error}`
          : "Starting up…"}
      </p>

      <ol className="steps">
        <li>Power on the Garmin Approach R50 and wait for its home screen.</li>
        <li>On the R50, choose <b>Simulator → GSPro</b> (Open Connect).</li>
        <li>Join the same Wi-Fi as this PC (the bay network).</li>
        <li>The R50 will connect automatically — the bar turns
            “Connected”. This app is already listening on port 921.</li>
      </ol>

      <h3>Not connecting?</h3>
      <ul className="troubleshoot">
        <li>Make sure GSPro itself is closed (it also uses port 921).</li>
        <li>Confirm both devices are on the same Wi-Fi.</li>
        <li>Tap reconnect to restart the listener.</li>
      </ul>
      <button onClick={cap.restart}>Reconnect</button>
    </main>
  );
}
