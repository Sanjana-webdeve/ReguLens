import { useEffect, useRef, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth.jsx";
import { Badge, Empty, Notice } from "../components/ui.jsx";

const REGULATORS = ["RBI", "Basel", "SEBI", "FATF", "Other"];
const CATEGORIES = ["KYC", "AML", "Digital Banking", "Customer Protection", "Capital Requirements", "Liquidity", "Risk Management", "General"];

export default function Documents() {
  const { can } = useAuth();
  const [docs, setDocs] = useState([]);
  const [filter, setFilter] = useState({ doc_type: "", regulator: "", q: "" });
  const [form, setForm] = useState({ doc_type: "regulation", regulator: "RBI", category: "KYC", version: "1", publication_date: "", name: "" });
  const [file, setFile] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef();

  const load = () => api.get("/documents", { params: filter }).then((r) => setDocs(r.data)).catch((e) => setErr(errMsg(e)));
  useEffect(() => { load(); }, [filter]);
  useEffect(() => {  // poll while anything is processing
    if (!docs.some((d) => d.status === "processing")) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [docs]);

  const upload = async (e) => {
    e.preventDefault();
    if (!file) return setErr("Choose a PDF, DOCX or TXT file first.");
    setErr(""); setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    Object.entries(form).forEach(([k, v]) => v && fd.append(k, v));
    try { await api.post("/documents", fd); setFile(null); fileRef.current.value = ""; load(); }
    catch (e) { setErr(errMsg(e)); }
    setBusy(false);
  };
  const del = async (d) => { if (confirm(`Delete "${d.name}" and everything extracted from it?`)) { await api.delete(`/documents/${d.id}`); load(); } };
  const reprocess = async (d) => { await api.post(`/documents/${d.id}/reprocess`); load(); };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const isPolicy = form.doc_type === "policy";

  return (
    <>
      <h1>Documents</h1>
      <Notice kind="error">{err}</Notice>
      {can("admin", "analyst") && (
        <form className="panel upload" onSubmit={upload}>
          <h2>Upload a document</h2>
          <div className="row">
            <label>Type<select value={form.doc_type} onChange={set("doc_type")}><option value="regulation">Regulation</option><option value="policy">Internal policy</option></select></label>
            <label>{isPolicy ? "Organisation" : "Regulator"}
              {isPolicy ? <input value={form.regulator} onChange={set("regulator")} placeholder="ABC Bank" /> :
                <input list="regs" value={form.regulator} onChange={set("regulator")} />}
              <datalist id="regs">{REGULATORS.map((r) => <option key={r} value={r} />)}</datalist></label>
            <label>Category<input list="cats" value={form.category} onChange={set("category")} /><datalist id="cats">{CATEGORIES.map((c) => <option key={c} value={c} />)}</datalist></label>
            <label>Version<input value={form.version} onChange={set("version")} /></label>
            <label>Publication date<input type="date" value={form.publication_date} onChange={set("publication_date")} /></label>
          </div>
          <div className="row">
            <label className="grow">Display name (optional)<input value={form.name} onChange={set("name")} placeholder="RBI KYC Direction 2025" /></label>
            <label className="grow">File<input ref={fileRef} type="file" accept=".pdf,.docx,.txt" onChange={(e) => setFile(e.target.files[0])} /></label>
            <button className="btn primary" disabled={busy}>{busy ? "Uploading…" : "Upload and process"}</button>
          </div>
        </form>
      )}

      <div className="row filters">
        <select value={filter.doc_type} onChange={(e) => setFilter({ ...filter, doc_type: e.target.value })}>
          <option value="">All documents</option><option value="regulation">Regulations</option><option value="policy">Policies</option></select>
        <input placeholder="Filter by name" value={filter.q} onChange={(e) => setFilter({ ...filter, q: e.target.value })} />
      </div>
      {docs.length === 0 ? <Empty title="No documents yet">Upload a regulation to get started.</Empty> : (
        <table className="tbl">
          <thead><tr><th>Name</th><th>Type</th><th>Regulator / org</th><th>Category</th><th>Version</th><th>Published</th><th>Uploaded</th><th>Status</th><th></th></tr></thead>
          <tbody>{docs.map((d) => (
            <tr key={d.id}>
              <td><strong>{d.name}</strong><div className="muted small">{d.page_count ? `${d.page_count} pages · ` : ""}{d.uploaded_by}</div>
                {d.status_message && <div className={d.status === "failed" ? "err small" : "muted small"}>{d.status_message}</div>}</td>
              <td>{d.doc_type}</td><td>{d.regulator}</td><td>{d.category}</td><td>{d.version}</td>
              <td>{d.publication_date || "–"}</td><td>{new Date(d.uploaded_at + "Z").toLocaleDateString()}</td>
              <td><Badge value={d.status} /></td>
              <td className="actions">{can("admin", "analyst") && <>
                {(d.status === "failed" || d.status_message) && <button className="link" onClick={() => reprocess(d)}>Re-process</button>}
                <button className="link danger" onClick={() => del(d)}>Delete</button></>}</td>
            </tr>))}</tbody>
        </table>
      )}
    </>
  );
}
