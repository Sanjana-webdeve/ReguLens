import { useEffect, useState } from "react";
import api from "../api";

export const STATUS_LABEL = {
  SATISFIED: "Satisfied", PARTIALLY_SATISFIED: "Partial", MISSING: "Missing", NOT_APPLICABLE: "Not applicable",
  NEW: "New", MODIFIED: "Modified", REMOVED: "Removed", UNCHANGED: "Unchanged",
  ready: "Ready", processing: "Processing", failed: "Failed",
};

export function Badge({ value }) {
  return <span className={`badge b-${value}`}>{STATUS_LABEL[value] || value}</span>;
}

export function Risk({ value }) {
  return value ? <span className={`risk r-${value}`}>{value}</span> : <span className="muted">–</span>;
}

export function Notice({ kind = "info", children }) {
  return children ? <div className={`notice n-${kind}`}>{children}</div> : null;
}

export function Empty({ title, children }) {
  return <div className="empty"><strong>{title}</strong><p>{children}</p></div>;
}

/** Click Source -> Section -> Page and read the underlying text (FR-06). */
export function SourceLink({ chunkId, label }) {
  const [open, setOpen] = useState(false);
  if (!chunkId) return <span className="muted">Not found</span>;
  return (
    <>
      <button className="cite" onClick={() => setOpen(true)}>{label}</button>
      {open && <EvidenceDrawer chunkId={chunkId} onClose={() => setOpen(false)} />}
    </>
  );
}

export function EvidenceDrawer({ chunkId, onClose }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.get(`/evidence/${chunkId}`).then((r) => setData(r.data)).catch(() => setErr("This evidence is no longer available."));
    const esc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [chunkId]);
  const Para = ({ c, dim }) => (
    <p className={dim ? "ev-dim" : "ev-main"}><span className="ev-sec">§ {c.section || "–"} · p.{c.page}</span>{c.text}</p>
  );
  return (
    <div className="scrim" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Evidence">
        <button className="close" onClick={onClose} aria-label="Close">×</button>
        {err && <Notice kind="error">{err}</Notice>}
        {!data && !err && <p className="muted">Loading evidence…</p>}
        {data && (
          <>
            <div className="ev-doc">{data.document.name}</div>
            <div className="ev-meta">
              {data.document.regulator && <span>{data.document.regulator}</span>}
              <span>Version {data.document.version}</span>
              <span>Section {data.chunk.section || "–"}</span>
              <span>Page {data.chunk.page}{data.chunk.page_end !== data.chunk.page ? `–${data.chunk.page_end}` : ""}</span>
            </div>
            {data.chunk.heading && <h3 className="ev-head">{data.chunk.heading}</h3>}
            {data.before.map((c) => <Para key={c.id} c={c} dim />)}
            <Para c={data.chunk} />
            {data.after.map((c) => <Para key={c.id} c={c} dim />)}
          </>
        )}
      </aside>
    </div>
  );
}
