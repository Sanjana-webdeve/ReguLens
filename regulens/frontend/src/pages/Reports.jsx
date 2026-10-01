import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { download, errMsg } from "../api";
import { Empty, Notice } from "../components/ui.jsx";

export default function Reports() {
  const [list, setList] = useState([]);
  const [err, setErr] = useState("");
  useEffect(() => { api.get("/comparisons").then((r) => setList(r.data.filter((c) => c.status === "completed"))); }, []);
  const get = (id, f) => download(`/reports/${id}?format=${f}`, `regulens_report_${id}.${f}`).catch((e) => setErr(errMsg(e)));
  return (
    <>
      <h1>Compliance reports</h1>
      <Notice kind="error">{err}</Notice>
      {list.length === 0 ? <Empty title="No completed assessments">Run a comparison first; each completed one can be exported here.</Empty> : (
        <table className="tbl">
          <thead><tr><th>Assessment</th><th>Date</th><th>Coverage</th><th>High-priority gaps</th><th>Export</th></tr></thead>
          <tbody>{list.map((c) => (
            <tr key={c.id}><td><Link to={`/compare/${c.id}`}>{c.regulation}</Link><div className="muted small">vs {c.policy}</div></td>
              <td>{new Date(c.created_at + "Z").toLocaleDateString()}</td><td>{c.summary.coverage_pct}%</td><td>{c.summary.high_priority_gaps}</td>
              <td className="actions">{["pdf", "csv", "json"].map((f) => <button key={f} className="link" onClick={() => get(c.id, f)}>{f.toUpperCase()}</button>)}</td></tr>))}</tbody>
        </table>)}
    </>
  );
}
