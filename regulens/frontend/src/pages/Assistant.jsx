import { useEffect, useRef, useState } from "react";
import api, { errMsg } from "../api";
import { Notice, SourceLink } from "../components/ui.jsx";

const pct = (v) => `${Math.round(v * 100)}%`;

function renderAnswer(text, citations) {
  // turn [n] markers into clickable source links
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (!m) return <span key={i}>{part}</span>;
    const c = citations.find((x) => x.n === +m[1]);
    return c ? <SourceLink key={i} chunkId={c.chunk_id} label={`[${c.n}]`} /> : <span key={i}>{part}</span>;
  });
}

export default function Assistant() {
  const [docs, setDocs] = useState([]);
  const [scope, setScope] = useState("");
  const [q, setQ] = useState("");
  const [thread, setThread] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const end = useRef();

  useEffect(() => { api.get("/documents").then((r) => setDocs(r.data.filter((d) => d.status === "ready"))); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [thread, busy]);

  const ask = async (e) => {
    e.preventDefault();
    const question = q.trim();
    if (!question) return;
    setQ(""); setErr(""); setBusy(true);
    setThread((t) => [...t, { role: "user", text: question }]);
    try {
      const r = await api.post("/qa", { question, document_ids: scope ? [+scope] : null });
      setThread((t) => [...t, { role: "ai", ...r.data }]);
    } catch (e) { setErr(errMsg(e)); }
    setBusy(false);
  };

  return (
    <div className="chat">
      <h1>Ask a question</h1>
      <div className="row"><label className="grow">Search in
        <select value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="">All documents</option>
          {docs.map((d) => <option key={d.id} value={d.id}>{d.name} (v{d.version})</option>)}
        </select></label></div>
      <div className="thread">
        {thread.length === 0 && <p className="muted">Try: “What are the requirements for customer due diligence?” Every answer lists its sources, and each source opens the original text.</p>}
        {thread.map((m, i) => m.role === "user" ? <div key={i} className="bubble user">{m.text}</div> : (
          <div key={i} className="bubble ai">
            {!m.llm_used && <Notice kind="warn">AI generation is unavailable right now. Showing the most relevant passages instead.</Notice>}
            <div className="answer">{renderAnswer(m.answer, m.citations)}</div>
            {m.citations.length > 0 && (
              <div className="sources"><h4>Sources</h4>
                {m.citations.map((c) => (
                  <div key={c.n} className={`src ${c.cited === false ? "uncited" : ""}`}>
                    <SourceLink chunkId={c.chunk_id} label={`[${c.n}] ${c.document} · §${c.section || "–"} · p.${c.page}`} />
                    <p>{c.snippet.slice(0, 220)}…</p>
                  </div>))}
              </div>)}
            {m.evaluation && (
              <div className="quality"><h4>AI response quality <small className="muted">({m.evaluation.method === "llm_judge" ? "LLM judge" : "lexical check"})</small></h4>
                <div className="qgrid">
                  <div><b>{pct(m.evaluation.grounding)}</b>grounding</div>
                  <div><b>{pct(m.evaluation.citation_accuracy)}</b>citation accuracy</div>
                  <div><b>{m.evaluation.retrieved_evidence}</b>evidence retrieved</div>
                  <div><b>{m.evaluation.unsupported_claims}</b>unsupported claims</div>
                </div></div>)}
          </div>))}
        {busy && <div className="bubble ai muted">Searching documents and drafting an answer…</div>}
        <div ref={end} />
      </div>
      <Notice kind="error">{err}</Notice>
      <form className="askbar" onSubmit={ask}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about a regulation or policy" maxLength={2000} />
        <button className="btn primary" disabled={busy}>Ask</button>
      </form>
    </div>
  );
}
