import { NavLink } from "react-router-dom";

const LINKS = [
  ["/", "Live"],
  ["/review", "Review"],
  ["/history", "History"],
  ["/sessions", "Sessions"],
  ["/players", "Players"],
  ["/sync", "Sync"],
];

export default function Sidebar() {
  return (
    <nav className="sidebar">
      {LINKS.map(([to, label]) => (
        <NavLink key={to} to={to} end={to === "/"}
          className={({ isActive }) => isActive ? "nav-row active" : "nav-row"}>
          {label}
        </NavLink>
      ))}
      <NavLink to="/connect" className="nav-row pinned">Connect / Settings</NavLink>
    </nav>
  );
}
