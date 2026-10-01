import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errMsg } from "../api";
import Chart from "../components/Plot.jsx";
import { Empty, Notice } from "../components/ui.jsx";

const pct = (v) => (v == null ? "–" : `${v}%`);

export default function Dashboard() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.get("/dashboard").then((r) => setD(r.data)).catch((e) => setErr(errMsg(e))); }, []);
  if (err) return <Notice kind="error">{err}</Notice>;
  if (!d) return <p className="muted">Loading…</p>;
  const c = d.counts, p = d.percent, hasData = d.status.SATISFIED + d.status.PARTIALLY_SATISFIED + d.status.MISSING > 0;

  return (
    <>
      <h1>Compliance overview</h1>
      <div className="ledger">
        <div><b>{c.regulations}</b><span>regulations</span></div>
        <div><b>{c.requirements}</b><span>requirements extracted</span></div>
        <div><b>{c.policies}</b><span>internal policies</span></div>
        <div><b>{c.comparisons}</b><span>compliance checks</span></div>
      </div>

      <div className="grid2">
        <section className="panel">
          <h2>Coverage of regulatory requirements</h2>
          {hasData ? (
            <Chart height={220} data={[{ type: "bar", orientation: "h", y: ["Satisfied", "Partial", "Missing"],
              x: [p.satisfied, p.partial, p.missing], text: [pct(p.satisfied), pct(p.partial), pct(p.missing)], textposition: "auto",
              marker: { color: ["#2F7D4F", "#B7791F", "#B3382C"] }, hoverinfo: "skip" }]}
              layout={{ xaxis: { range: [0, 100], ticksuffix: "%" }, yaxis: { autorange: "reversed" }, margin: { l: 70, r: 10, t: 10, b: 30 } }} />
          ) : <Empty title="No comparisons yet">Upload a regulation and a policy, then <Link to="/compare">run a comparison</Link>.</Empty>}
        </section>
        <section className="panel">
          <h2>High-priority gaps</h2>
          {d.top_gaps.length ? (
            <ol className="plain">{d.top_gaps.map((g) => (
              <li key={g.gap_code}><Link to={`/compare/${g.comparison_id}`}><code>{g.gap_code}</code> {g.requirement}</Link></li>
            ))}</ol>
          ) : <p className="muted">No high-priority gaps found.</p>}
        </section>
      </div>

      <div className="grid2">
        <section className="panel">
          <h2>AI answer quality <small className="muted">(last {d.ai_quality.samples} answers)</small></h2>
          {d.ai_quality.samples ? (
            <table className="kv"><tbody>
              <tr><td>Grounding</td><td>{pct(d.ai_quality.grounding)}</td></tr>
              <tr><td>Citation accuracy</td><td>{pct(d.ai_quality.citation_accuracy)}</td></tr>
              <tr><td>Relevance</td><td>{pct(d.ai_quality.relevance)}</td></tr>
            </tbody></table>
          ) : <p className="muted">Ask a question to start collecting quality scores.</p>}
        </section>
        <section className="panel">
          <h2>Recent activity</h2>
          <ul className="plain small">{d.recent_activity.map((a, i) => (
            <li key={i}><span className="muted">{new Date(a.time + "Z").toLocaleTimeString()}</span> {a.user.split("@")[0]} · {a.action}</li>
          ))}</ul>
        </section>
      </div>
    </>
  );
}
