import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth } from "../auth.jsx";
import { Badge, Empty, Notice } from "../components/ui.jsx";

export default function Compare() {
  const { can } = useAuth();
  const nav = useNavigate();
  const [regs, setRegs] = useState([]);
  const [pols, setPols] = useState([]);
  const [sel, setSel] = useState({ regulation_id: "", policy_id: "" });
  const [list, setList] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/comparisons").then((r) => setList(r.data));
  useEffect(() => {
    api.get("/documents", { params: { doc_type: "regulation" } }).then((r) => setRegs(r.data.filter((d) => d.status === "ready")));
    api.get("/documents", { params: { doc_type: "policy" } }).then((r) => setPols(r.data.filter((d) => d.status === "ready")));
    load();
  }, []);
  useEffect(() => {
    if (!list.some((c) => c.status === "running")) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [list]);

  const run = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { const r = await api.post("/comparisons", { regulation_id: +sel.regulation_id, policy_id: +sel.policy_id }); nav(`/compare/${r.data.id}`); }
    catch (e) { setErr(errMsg(e)); }
    setBusy(false);
  };

  return (
    <>
      <h1>Compare a regulation with a policy</h1>
      <Notice kind="error">{err}</Notice>
      {can("admin", "analyst") && (
        <form className="panel row" onSubmit={run}>
          <label className="grow">Regulation
            <select required value={sel.regulation_id} onChange={(e) => setSel({ ...sel, regulation_id: e.target.value })}>
              <option value="">Select…</option>{regs.map((d) => <option key={d.id} value={d.id}>{d.name} (v{d.version})</option>)}</select></label>
          <label className="grow">Internal policy
            <select required value={sel.policy_id} onChange={(e) => setSel({ ...sel, policy_id: e.target.value })}>
              <option value="">Select…</option>{pols.map((d) => <option key={d.id} value={d.id}>{d.name} (v{d.version})</option>)}</select></label>
          <button className="btn primary" disabled={busy}>Run comparison</button>
        </form>)}
      <h2>Previous checks</h2>
      {list.length === 0 ? <Empty title="No comparisons yet">Choose a regulation and a policy above.</Empty> : (
        <table className="tbl">
          <thead><tr><th>#</th><th>Regulation</th><th>Policy</th><th>Status</th><th>Coverage</th><th>High-priority gaps</th><th>Run</th></tr></thead>
          <tbody>{list.map((c) => (
            <tr key={c.id}><td><Link to={`/compare/${c.id}`}>{c.id}</Link></td><td>{c.regulation}</td><td>{c.policy}</td>
              <td>{c.status === "running" ? `Running ${c.done}/${c.total}` : <Badge value={c.status === "completed" ? "ready" : c.status} />}</td>
              <td>{c.summary ? `${c.summary.coverage_pct}%` : "–"}</td><td>{c.summary ? c.summary.high_priority_gaps : "–"}</td>
              <td>{new Date(c.created_at + "Z").toLocaleString()}</td></tr>))}</tbody>
        </table>)}
    </>
  );
}
