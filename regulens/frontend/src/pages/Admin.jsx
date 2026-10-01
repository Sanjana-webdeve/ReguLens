import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { Notice } from "../components/ui.jsx";

const ROLES = ["admin", "analyst", "auditor", "viewer"];

export default function Admin() {
  const [users, setUsers] = useState([]);
  const [m, setM] = useState(null);
  const [err, setErr] = useState("");
  const load = () => {
    api.get("/auth/users").then((r) => setUsers(r.data)).catch((e) => setErr(errMsg(e)));
    api.get("/admin/metrics").then((r) => setM(r.data));
  };
  useEffect(load, []);
  const patch = async (id, body) => { try { await api.patch(`/auth/users/${id}`, body); load(); } catch (e) { setErr(errMsg(e)); } };
  return (
    <>
      <h1>Administration</h1>
      <Notice kind="error">{err}</Notice>
      <h2>Users and roles</h2>
      <table className="tbl">
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Active</th></tr></thead>
        <tbody>{users.map((u) => (
          <tr key={u.id}><td>{u.full_name}</td><td>{u.email}</td>
            <td><select value={u.role} onChange={(e) => patch(u.id, { role: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></td>
            <td><input type="checkbox" checked={u.is_active} onChange={(e) => patch(u.id, { is_active: e.target.checked })} /></td></tr>))}</tbody>
      </table>
      <h2>System health</h2>
      {m && (
        <div className="grid2">
          <section className="panel"><h3>Latency (ms)</h3>
            <table className="kv"><tbody>{Object.entries(m.latency_ms).map(([k, v]) => <tr key={k}><td>{k}</td><td>avg {v.avg} · p95 {v.p95} · n={v.count}</td></tr>)}</tbody></table></section>
          <section className="panel"><h3>Counters</h3>
            <table className="kv"><tbody>{Object.entries(m.counters).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v}</td></tr>)}</tbody></table></section>
        </div>)}
    </>
  );
}
