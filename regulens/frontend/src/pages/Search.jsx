import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api, { errMsg } from "../api";
import { Badge, Empty, Notice, SourceLink } from "../components/ui.jsx";

export default function Search() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") || "");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const term = sp.get("q");
    setQ(term || "");
    if (!term) return;
    api.get("/search", { params: { q: term } }).then((r) => setRes(r.data)).catch((e) => setErr(errMsg(e)));
  }, [sp]);

  const total = res ? res.documents.length + res.sections.length + res.requirements.length + res.gaps.length : 0;
  return (
    <>
      <h1>Search</h1>
      <form className="row" onSubmit={(e) => { e.preventDefault(); setSp({ q }); }}>
        <input className="grow" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. beneficial ownership" />
        <button className="btn primary">Search</button>
      </form>
      <Notice kind="error">{err}</Notice>
      {res && total === 0 && <Empty title="No results">Try different words, or check that your documents have finished processing.</Empty>}
      {res && res.documents.length > 0 && <section><h2>Documents</h2><ul className="plain">{res.documents.map((d) => (
        <li key={d.id}><strong>{d.name}</strong> <span className="muted">{d.regulator} · {d.category} · v{d.version} · {d.doc_type}</span></li>))}</ul></section>}
      {res && res.sections.length > 0 && <section><h2>Sections</h2><ul className="plain">{res.sections.map((s) => (
        <li key={s.chunk_id}><strong>{s.document}</strong> — <SourceLink chunkId={s.chunk_id} label={`Section ${s.section || "–"}, page ${s.page}`} /><div className="small muted">{s.text}…</div></li>))}</ul></section>}
      {res && res.requirements.length > 0 && <section><h2>Requirements</h2><ul className="plain">{res.requirements.map((r) => (
        <li key={r.id}><code>{r.code}</code> {r.text} <SourceLink chunkId={r.chunk_id} label={`§${r.section || "–"} · p.${r.page}`} /></li>))}</ul></section>}
      {res && res.gaps.length > 0 && <section><h2>Compliance gaps</h2><ul className="plain">{res.gaps.map((g) => (
        <li key={g.id}><Link to={`/compare/${g.comparison_id}`}><code>{g.gap_code}</code></Link> <Badge value={g.status} /> {g.requirement}</li>))}</ul></section>}
    </>
  );
}
