import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { Badge, Empty, Notice, SourceLink } from "../components/ui.jsx";

export default function Versions() {
  const [fams, setFams] = useState([]);
  const [docs, setDocs] = useState([]);
  const [sel, setSel] = useState({ old_id: "", new_id: "" });
  const [res, setRes] = useState(null);
  const [show, setShow] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/versions/families").then((r) => setFams(r.data));
    api.get("/documents", { params: { doc_type: "regulation" } }).then((r) => setDocs(r.data.filter((d) => d.status === "ready")));
  }, []);

  const run = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true); setRes(null);
    try { setRes((await api.post("/versions/diff", { old_id: +sel.old_id, new_id: +sel.new_id })).data); }
    catch (e) { setErr(errMsg(e)); }
    setBusy(false);
  };
  const shown = res ? res.changes.filter((c) => !show || c.change === show) : [];

  return (
    <>
      <h1>What changed between versions?</h1>
      <Notice kind="error">{err}</Notice>
      <form className="panel row" onSubmit={run}>
        <label className="grow">Earlier version<select required value={sel.old_id} onChange={(e) => setSel({ ...sel, old_id: e.target.value })}>
          <option value="">Select…</option>{docs.map((d) => <option key={d.id} value={d.id}>{d.name} (v{d.version})</option>)}</select></label>
        <label className="grow">Newer version<select required value={sel.new_id} onChange={(e) => setSel({ ...sel, new_id: e.target.value })}>
          <option value="">Select…</option>{docs.map((d) => <option key={d.id} value={d.id}>{d.name} (v{d.version})</option>)}</select></label>
        <button className="btn primary" disabled={busy}>{busy ? "Comparing…" : "Detect changes"}</button>
      </form>

      {!res && fams.length > 0 && (
        <section><h2>Document families</h2>
          {fams.map((f) => <div key={f.key} className="fam"><strong>{f.regulator || "—"}</strong>{f.versions.map((v) => <span key={v.id} className="chip">{v.name} · v{v.version}</span>)}</div>)}
        </section>)}

      {res && (
        <>
          <div className="ledger">{["NEW", "MODIFIED", "REMOVED", "UNCHANGED"].map((k) => (
            <div key={k} role="button" onClick={() => setShow(show === k ? "" : k)} className={show === k ? "on" : ""}><b>{res.counts[k]}</b><span>{k.toLowerCase()}</span></div>))}</div>
          {shown.length === 0 ? <Empty title="Nothing to show">No changes in this category.</Empty> : (
            <table className="tbl">
              <thead><tr><th>Change</th><th>Requirement</th><th>Previous ({res.old.name} v{res.old.version})</th><th>Current ({res.new.name} v{res.new.version})</th></tr></thead>
              <tbody>{shown.map((c, i) => (
                <tr key={i}><td><Badge value={c.change} /><div className="muted small">sim {c.similarity}</div></td>
                  <td>{(c.current || c.previous).text}{c.summary && <div className="small"><strong>What changed:</strong> {c.summary}</div>}</td>
                  <td>{c.previous ? <SourceLink chunkId={c.previous.chunk_id} label={`§${c.previous.section || "–"} · p.${c.previous.page}`} /> : <span className="muted">Not present</span>}</td>
                  <td>{c.current ? <SourceLink chunkId={c.current.chunk_id} label={`§${c.current.section || "–"} · p.${c.current.page}`} /> : <span className="muted">Removed</span>}</td></tr>))}</tbody>
            </table>)}
        </>)}
    </>
  );
}
