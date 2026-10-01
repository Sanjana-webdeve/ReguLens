import { Fragment, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api, { download, errMsg } from "../api";
import { useAuth } from "../auth.jsx";
import Chart from "../components/Plot.jsx";
import { Badge, Notice, Risk, SourceLink } from "../components/ui.jsx";

export default function ComparisonDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const [c, setC] = useState(null);
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState("");

  const load = async () => {
    try {
      const a = await api.get(`/comparisons/${id}`);
      setC(a.data);
      const b = await api.get(`/comparisons/${id}/results`);
      setRows(b.data);
    } catch (e) { setErr(errMsg(e)); }
  };
  useEffect(() => { load(); }, [id]);
  useEffect(() => {
    if (c?.status !== "running") return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [c?.status]);

  if (err) return <Notice kind="error">{err}</Notice>;
  if (!c) return <p className="muted">Loading…</p>;
  const s = c.summary;
  const shown = rows.filter((r) => !filter || r.status === filter || r.risk === filter);

  return (
    <>
      <h1>{c.regulation}</h1>
      <p className="muted">checked against <strong>{c.policy}</strong></p>
      {c.status === "running" && <Notice kind="info">Analysis in progress: {c.done} of {c.total} requirements checked.</Notice>}
      {c.status === "failed" && <Notice kind="error">{c.error}</Notice>}
      {!c.used_llm && c.status !== "running" && <Notice kind="warn">The AI reviewer was unavailable, so statuses come from semantic matching alone. Review them manually before relying on them.</Notice>}
      <Notice kind="info">{c.disclaimer}</Notice>

      <div className="grid2">
        <section className="panel">
          <h2>Coverage {s.coverage_pct}%</h2>
          <Chart height={200} data={[{ type: "pie", hole: 0.55, labels: ["Satisfied", "Partial", "Missing", "Not applicable"],
            values: Object.values(s.counts), marker: { colors: ["#2F7D4F", "#B7791F", "#B3382C", "#9AA5AD"] }, sort: false, textinfo: "value" }]}
            layout={{ margin: { l: 10, r: 10, t: 10, b: 10 } }} />
        </section>
        <section className="panel">
          <h2>Summary</h2>
          <table className="kv"><tbody>
            <tr><td>Satisfied</td><td>{s.satisfied_pct}%</td></tr><tr><td>Partially satisfied</td><td>{s.partial_pct}%</td></tr>
            <tr><td>Missing</td><td>{s.missing_pct}%</td></tr>
            <tr><td>High / medium / low gaps</td><td>{s.high_priority_gaps} / {s.medium_gaps} / {s.low_gaps}</td></tr></tbody></table>
          {c.status === "completed" && can("admin", "analyst", "auditor") && (
            <div className="row">{["pdf", "csv", "json"].map((f) => (
              <button key={f} className="btn" onClick={() => download(`/reports/${c.id}?format=${f}`, `regulens_report_${c.id}.${f}`).catch((e) => setErr(errMsg(e)))}>Export {f.toUpperCase()}</button>))}</div>)}
        </section>
      </div>

      <div className="row filters">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All findings</option><option value="SATISFIED">Satisfied</option><option value="PARTIALLY_SATISFIED">Partial</option>
          <option value="MISSING">Missing</option><option value="NOT_APPLICABLE">Not applicable</option><option value="HIGH">High risk</option><option value="MEDIUM">Medium risk</option></select>
      </div>
      <table className="tbl">
        <thead><tr><th>Requirement</th><th>Regulatory source</th><th>Policy coverage</th><th>Status</th><th>Risk</th></tr></thead>
        <tbody>{shown.map((r) => (
          <Fragment key={r.id}>
            <tr key={r.id} className="clickable" onClick={() => setOpen(open === r.id ? null : r.id)}>
              <td><code>{r.gap_code || r.requirement_code}</code> {r.requirement}</td>
              <td onClick={(e) => e.stopPropagation()}><SourceLink chunkId={r.reg_chunk_id} label={`§${r.reg_section || "–"} · p.${r.reg_page}`} /></td>
              <td onClick={(e) => e.stopPropagation()}>{r.policy_chunk_id ? <SourceLink chunkId={r.policy_chunk_id} label={`§${r.policy_section || "–"} · p.${r.policy_page}`} /> : <span className="muted">Not found</span>}</td>
              <td><Badge value={r.status} /></td><td><Risk value={r.risk} /></td></tr>
            {open === r.id && (
              <tr key={`${r.id}d`} className="detail"><td colSpan={5}>
                <p><strong>Reasoning:</strong> {r.rationale}</p>
                {r.recommendation && <p><strong>Recommendation:</strong> {r.recommendation}<br /><span className="muted">Regulatory basis: §{r.reg_section || "–"}, page {r.reg_page}</span></p>}
                {r.risk_factors.length > 0 && <p className="small muted">Risk factors: {r.risk_factors.join(" · ")}</p>}
                {r.evidence_text && <blockquote>{r.evidence_text.slice(0, 600)}</blockquote>}
                <p className="small muted">Method: {r.method} · similarity {r.similarity}</p>
              </td></tr>)}
          </Fragment>))}</tbody>
      </table>
    </>
  );
}
