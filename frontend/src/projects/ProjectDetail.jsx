import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import Modal from "../components/Modal";
import {
  PRIORITIES,
  REQ_STATUSES,
  REQ_TYPES,
  REQ_TYPE_LABEL,
  label,
} from "../requirements/constants";

const PRIORITY_CHIP = { high: "chip-red", medium: "chip-amber", low: "chip-grey" };
const PRIORITY_DOT = { high: "#dc2626", medium: "#d97706", low: "#94a3b8" };

function relTime(iso) {
  if (!iso) return "";
  const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const t = then.getTime();
  if (Number.isNaN(t)) return "";
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  if (d === 1) return "yesterday";
  if (d < 30) return `${d}d ago`;
  return then.toLocaleDateString();
}

export default function ProjectDetail() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // add-requirement modal
  const [modalOpen, setModalOpen] = useState(false);
  const [tab, setTab] = useState("write"); // "write" | "upload"

  // write form
  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [reqType, setReqType] = useState("user_story");
  const [priority, setPriority] = useState("medium");
  const [status, setStatus] = useState("draft");
  const [saving, setSaving] = useState(false);

  // upload form
  const fileRef = useRef(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadType, setUploadType] = useState("feature_description");
  const [uploading, setUploading] = useState(false);

  // list controls
  const [query, setQuery] = useState("");
  const [prioFilter, setPrioFilter] = useState("all"); // all | high | medium | low
  const [confirmId, setConfirmId] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const [p, r] = await Promise.all([
        api.getProject(projectId),
        api.listRequirements(projectId),
      ]);
      setProject(p);
      setRequirements(r);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [projectId]);

  function openModal() {
    setError("");
    setModalOpen(true);
  }

  async function onCreate(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await api.createRequirement(projectId, {
        title,
        raw_text: rawText,
        req_type: reqType,
        priority,
        status,
      });
      setTitle("");
      setRawText("");
      setModalOpen(false);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function onUpload(e) {
    e.preventDefault();
    setError("");
    const f = fileRef.current?.files?.[0];
    if (!f) {
      setError("Choose a file to upload.");
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      if (uploadTitle) fd.append("title", uploadTitle);
      fd.append("req_type", uploadType);
      await api.uploadRequirement(projectId, fd);
      setUploadTitle("");
      if (fileRef.current) fileRef.current.value = "";
      setModalOpen(false);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function onDelete(id) {
    try {
      await api.deleteRequirement(projectId, id);
      setConfirmId(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const highCount = requirements.filter((r) => r.priority === "high").length;
  const readyCount = requirements.filter(
    (r) => r.status === "ready" || r.status === "done"
  ).length;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return requirements.filter((r) => {
      if (prioFilter !== "all" && r.priority !== prioFilter) return false;
      if (!q) return true;
      return (
        (r.title || "").toLowerCase().includes(q) ||
        (r.raw_text || "").toLowerCase().includes(q)
      );
    });
  }, [requirements, query, prioFilter]);

  if (loading)
    return (
      <div className="content">
        <p className="muted">Loading…</p>
      </div>
    );

  return (
    <div className="content proj-detail">
      <p className="crumb">
        <Link to="/projects">Projects</Link>
        <span className="sep">/</span>
        <span>{project?.name}</span>
      </p>

      <header className="pd-head">
        <div className="pd-head-main">
          <h1>{project?.name}</h1>
          <p className="sub">
            {project?.description ||
              "Add requirements in any source form, then open one to run the AI test-design pipeline."}
          </p>
        </div>
        <button className="btn-primary" onClick={openModal}>
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
            <path d="M8 3v10M3 8h10" />
          </svg>
          New requirement
        </button>
      </header>

      <section className="pd-stats">
        <div className="pd-stat">
          <span className="v">{requirements.length}</span>
          <span className="k">Requirements</span>
        </div>
        <div className="pd-stat">
          <span className="v">{highCount}</span>
          <span className="k">High priority</span>
        </div>
        <div className="pd-stat">
          <span className="v">{readyCount}</span>
          <span className="k">Ready / done</span>
        </div>
      </section>

      {error && !modalOpen && <p className="error">{error}</p>}

      {requirements.length === 0 ? (
        <div className="empty">
          <h3>No requirements yet</h3>
          <p>Add your first requirement to start the AI test-design pipeline.</p>
          <button className="btn-primary" onClick={openModal} style={{ margin: "0 auto" }}>
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
              <path d="M8 3v10M3 8h10" />
            </svg>
            New requirement
          </button>
        </div>
      ) : (
        <>
          <div className="pd-toolbar">
            <div className="pd-search">
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                <circle cx="7" cy="7" r="4.2" />
                <path d="M10.2 10.2 14 14" />
              </svg>
              <input
                placeholder="Search requirements…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div className="pd-filters">
              {["all", "high", "medium", "low"].map((p) => (
                <button
                  key={p}
                  className={`pd-filter ${prioFilter === p ? "active" : ""}`}
                  onClick={() => setPrioFilter(p)}
                >
                  {p === "all" ? "All" : p[0].toUpperCase() + p.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {filtered.length === 0 ? (
            <p className="muted" style={{ padding: "24px 4px" }}>
              No requirements match your search.
            </p>
          ) : (
            <div className="req-list">
              {filtered.map((r) => (
                <div
                  className="req-row"
                  key={r.id}
                  onClick={() => navigate(`/projects/${projectId}/requirements/${r.id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter")
                      navigate(`/projects/${projectId}/requirements/${r.id}`);
                  }}
                >
                  <span
                    className="req-dot"
                    style={{ background: PRIORITY_DOT[r.priority] || "#94a3b8" }}
                    title={`${r.priority} priority`}
                  />
                  <div className="req-main">
                    <div className="req-title-line">
                      <span className="req-title">{r.title}</span>
                      <span className="chip chip-accent">
                        {REQ_TYPE_LABEL[r.req_type] || r.req_type}
                      </span>
                      <span className={`chip ${PRIORITY_CHIP[r.priority] || "chip-grey"}`}>
                        {r.priority}
                      </span>
                      <span className="chip chip-grey">{label({}, r.status)}</span>
                      {r.source_filename && (
                        <span className="chip chip-grey" title={r.source_filename}>
                          📎 file
                        </span>
                      )}
                    </div>
                    {r.raw_text && <p className="req-snip">{r.raw_text}</p>}
                  </div>
                  <div className="req-side" onClick={(e) => e.stopPropagation()}>
                    {r.created_at && <span className="req-time">{relTime(r.created_at)}</span>}
                    {confirmId === r.id ? (
                      <span className="req-confirm">
                        <span>Delete?</span>
                        <button className="solid-danger btn-sm" onClick={() => onDelete(r.id)}>
                          Yes
                        </button>
                        <button className="ghost btn-sm" onClick={() => setConfirmId(null)}>
                          No
                        </button>
                      </span>
                    ) : (
                      <>
                        <Link
                          className="req-open"
                          to={`/projects/${projectId}/requirements/${r.id}`}
                        >
                          Open
                          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M6 4l4 4-4 4" />
                          </svg>
                        </Link>
                        <button
                          className="icon-btn danger req-del"
                          title="Delete requirement"
                          aria-label="Delete requirement"
                          onClick={() => setConfirmId(r.id)}
                        >
                          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M2.8 4.2h10.4M6 4.2V2.9h4v1.3M5 4.2l.5 9h5l.5-9" />
                            <path d="M6.7 6.6v4.2M9.3 6.6v4.2" />
                          </svg>
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="New requirement"
        subtitle="Write it directly, or upload a document — then open it to run the AI pipeline."
        width={600}
      >
        <div className="seg" role="tablist">
          <button
            type="button"
            className={tab === "write" ? "active" : ""}
            onClick={() => setTab("write")}
          >
            Write
          </button>
          <button
            type="button"
            className={tab === "upload" ? "active" : ""}
            onClick={() => setTab("upload")}
          >
            Upload
          </button>
        </div>

        {tab === "write" ? (
          <form className="form-v" onSubmit={onCreate}>
            <label className="field">
              Title
              <input
                placeholder="e.g. Secure sign in"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                autoFocus
              />
            </label>
            <label className="field">
              Type
              <select value={reqType} onChange={(e) => setReqType(e.target.value)}>
                {REQ_TYPES.map((t) => (
                  <option key={t} value={t}>{REQ_TYPE_LABEL[t]}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Requirement text
              <textarea
                placeholder="As a user, I want to… / BRD / PRD / use case text…"
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                rows={6}
                required
              />
            </label>
            <div className="field-row">
              <label className="field">
                Priority
                <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                Status
                <select value={status} onChange={(e) => setStatus(e.target.value)}>
                  {REQ_STATUSES.map((s) => (
                    <option key={s} value={s}>{label({}, s)}</option>
                  ))}
                </select>
              </label>
            </div>
            {error && <p className="error">{error}</p>}
            <div className="modal-actions">
              <button type="button" className="ghost" onClick={() => setModalOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? "Adding…" : "Add requirement"}
              </button>
            </div>
          </form>
        ) : (
          <form className="form-v" onSubmit={onUpload}>
            <p className="form-hint">
              Upload a requirement document. Text files (.txt/.md/.csv) are extracted
              automatically; other formats are attached for you to edit.
            </p>
            <label className="field">
              Title <span className="muted" style={{ fontWeight: 400 }}>(optional)</span>
              <input
                placeholder="Defaults to the file name"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
              />
            </label>
            <label className="field">
              Type
              <select value={uploadType} onChange={(e) => setUploadType(e.target.value)}>
                {REQ_TYPES.map((t) => (
                  <option key={t} value={t}>{REQ_TYPE_LABEL[t]}</option>
                ))}
              </select>
            </label>
            <label className="field">
              File
              <input type="file" ref={fileRef} />
            </label>
            {error && <p className="error">{error}</p>}
            <div className="modal-actions">
              <button type="button" className="ghost" onClick={() => setModalOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={uploading}>
                {uploading ? "Uploading…" : "Upload requirement"}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
