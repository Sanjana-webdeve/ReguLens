import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

const NAV = [
  ["/", "Dashboard"],
  ["/documents", "Documents"],
  ["/assistant", "Ask a question"],
  ["/requirements", "Requirements"],
  ["/compare", "Compare & gaps"],
  ["/versions", "Version changes"],
  ["/search", "Search"],
  ["/reports", "Reports", ["admin", "analyst", "auditor"]],
  ["/audit", "Audit trail", ["admin", "auditor"]],
  ["/admin", "Administration", ["admin"]],
];

export default function Layout() {
  const { user, logout, can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">ReguLens</div>
        <nav>
          {NAV.filter(([, , roles]) => !roles || can(...roles)).map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>
          ))}
        </nav>
        <div className="side-foot">
          <div>{user.full_name}</div>
          <div className="muted-dark">{user.role}</div>
          <button className="link-dark" onClick={async () => { await logout(); nav("/login"); }}>Log out</button>
        </div>
      </aside>
      <main>
        <form className="topsearch" onSubmit={(e) => { e.preventDefault(); if (q.trim()) nav(`/search?q=${encodeURIComponent(q)}`); }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search regulations, policies, requirements, gaps" aria-label="Search" />
        </form>
        <div className="page"><Outlet /></div>
      </main>
    </div>
  );
}
