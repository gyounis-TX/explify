import { NavLink } from "react-router-dom";
import "./Sidebar.css";

const navItems = [
  { path: "/", label: "Import" },
  { path: "/results", label: "Report Explanation" },
  { path: "/letters", label: "Letters" },
  { path: "/history", label: "History" },
  { path: "/templates", label: "Templates" },
  { path: "/settings", label: "Settings" },
  { path: "/ai-model", label: "AI Model" },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1 className="sidebar-title">Explify</h1>
      </div>
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? "sidebar-link--active" : ""}`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
