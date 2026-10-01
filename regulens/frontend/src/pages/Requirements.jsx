import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { Empty, Notice, SourceLink } from "../components/ui.jsx";

export default function Requirements() {
  const [rows, setRows] = useState([]);
  const [docs, setDocs] = useState([]);
  const [cats, setCats] = useState([]);
  const [f, setF] = useState({ document_id: "", category: "", mandatory: "", q: "" });
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get("/documents", { params: { doc_type: "regulation" } }).then((r) => setDocs(r.data));
    api.get("/requirements/categories").then((r) => setCats(r.data));
  }, []);
  useEffect(() => {
    const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v !== ""));
    api.get("/requirements", { params }).then((r) => setRows(r.data)).catch((e) => setErr(errMsg(e)));
  }, [f]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  return (
    <>
      <h1>Regulatory requirements</h1>
      <Notice kind="error">{err}</Notice>
      <div className="row filters">
        <select value={f.document_id} onChange={set("document_id")}><option value="">All regulations</option>{docs.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
        <select value={f.category} onChange={set("category")}><option value="">All categories</option>{cats.map((c) => <option key={c.category} value={c.category}>{c.category} ({c.count})</option>)}</select>
        <select value={f.mandatory} onChange={set("mandatory")}><option value="">Mandatory and optional</option><option value="true">Mandatory</option><option value="false">Optional</option></select>
        <input placeholder="Search text" value={f.q} onChange={set("q")} />
      </div>
      {rows.length === 0 ? <Empty title="No requirements found">Requirements are extracted automatically when a regulation finishes processing.</Empty> : (
        <table className="tbl">
          <thead><tr><th>ID</th><th>Requirement</th><th>Category</th><th>Mandatory</th><th>Source</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.id}><td><code>{r.code}</code></td>
              <td><strong>{r.title}</strong><div>{r.requirement}</div></td>
              <td>{r.category}</td><td>{r.mandatory ? "Yes" : "No"}</td>
              <td><div className="small">{r.source}</div><SourceLink chunkId={r.chunk_id} label={`§${r.section || "–"} · p.${r.page}`} /></td></tr>))}</tbody>
        </table>)}
    </>
  );
}
