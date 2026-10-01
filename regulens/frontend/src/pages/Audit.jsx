import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { Empty, Notice } from "../components/ui.jsx";

export default function Audit() {
  const [rows, setRows] = useState([]);
  const [f, setF] = useState({ action: "", username: "" });
  const [err, setErr] = useState("");
  useEffect(() => { api.get("/audit", { params: { ...f, limit: 200 } }).then((r) => setRows(r.data)).catch((e) => setErr(errMsg(e))); }, [f]);
  return (
    <>
      <h1>Audit trail</h1>
      <Notice kind="error">{err}</Notice>
      <div className="row filters">
        <input placeholder="Filter by action (e.g. document.upload)" value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })} />
        <input placeholder="Filter by user" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} />
      </div>
      {rows.length === 0 ? <Empty title="No matching events">Actions such as uploads, comparisons and reports appear here.</Empty> : (
        <table className="tbl">
          <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Resource</th><th>Details</th><th>Result</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.id}><td>{new Date(r.time + "Z").toLocaleString()}</td><td>{r.user}</td><td><code>{r.action}</code></td>
              <td>{r.resource_type} {r.resource_id}</td><td className="small">{JSON.stringify(r.details)}</td>
              <td className={r.result === "success" ? "" : "err"}>{r.result}</td></tr>))}</tbody>
        </table>)}
    </>
  );
}
