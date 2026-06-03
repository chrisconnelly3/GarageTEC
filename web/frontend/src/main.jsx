import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function Boot() {
  return <main><h1>GarageTEC</h1><p>Loading…</p></main>;
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Boot />
  </React.StrictMode>
);
