import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import {
  PRIORITIES,
  REQ_STATUSES,
  REQ_TYPES,
  REQ_TYPE_LABEL,
  label,
} from "../requirements/constants";

export default function ModuleDetail() {
  const { projectId, moduleId } = useParams();
  const [module, setModule] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [tab, setTab] = useState("write"); // "write" | "upload"
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // write form
  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [reqType, setReqType] = useState("user_story");
  const [priority, setPriority] = useState("medium");
  const [status, setStatus] = useState("draft");

  // upload form
  const fileRef = useRef(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadType, setUploadType] = useState("feature_description");
  const [uploading, setUploading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [m, r] = await Promise.all([
        api.getModule(projectId, moduleId),
        api.listRequirements(projectId, moduleId),
      ]);
      setModule(m);
      setRequirements(r);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [projectId, moduleId]);

  async function onCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createRequirement(projectId, moduleId, {
        title,
        raw_text: rawText,
        req_type: reqType,
        priority,
        status,
      });
      setTitle("");
      setRawText("");
      await load();
    } catch (err) {
      setError(err.message);
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
      await api.uploadRequirement(projectId, moduleId, fd);
      setUploadTitle("");
      if (fileRef.current) fileRef.current.value = "";
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function onDelete(id) {
    if (!confirm("Delete this requirement and its generated artifacts?")) return;
    await api.deleteRequirement(projectId, id);
    await load();
  }

  if (loading)
    return (
      <div className="content">
        <p className="muted">Loading…</p>
      </div>
    );

  return (
    <div className="content project-content">
      <div className="page project-page">
        <p className="breadcrumb">
          <Link to="/">Home</Link> /{" "}
          <Link to={`/projects/${projectId}`}>Project</Link> / {module?.name}
        </p>
        <header className="project-page-head">
          <div>
            <div className="eyebrow">Module</div>
            <h1>{module?.name}</h1>
            <p>{module?.description || "Add requirements in any source form, then open one to run the AI test-design pipeline."}</p>
          </div>
          <div className="story-count">
            <strong>{requirements.length}</strong>
            <span>{requirements.length === 1 ? "requirement" : "requirements"}</span>
          </div>
        </header>

        <div className="stories-workspace">
          <aside className="story-composer">
            <div className="panel-kicker">New requirement</div>
            <div className="mode-toggle" role="tablist" style={{ marginBottom: 12 }}>
              <button
                className={`mode-btn ${tab === "write" ? "active" : ""}`}
                onClick={() => setTab("write")}
              >
                Write
              </button>
              <button
                className={`mode-btn ${tab === "upload" ? "active" : ""}`}
                onClick={() => setTab("upload")}
              >
                Upload document
              </button>
            </div>

            {tab === "write" ? (
              <form className="story-form" onSubmit={onCreate}>
                <label>
                  Title
                  <input
                    placeholder="e.g. Secure sign in"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Type
                  <select value={reqType} onChange={(e) => setReqType(e.target.value)}>
                    {REQ_TYPES.map((t) => (
                      <option key={t} value={t}>{REQ_TYPE_LABEL[t]}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Requirement text
                  <textarea
                    placeholder="As a user, I want to… / BRD / PRD / use case text…"
                    value={rawText}
                    onChange={(e) => setRawText(e.target.value)}
                    rows={7}
                    required
                  />
                </label>
                <div className="inline-edit-row">
                  <label style={{ flex: 1 }}>
                    Priority
                    <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                      {PRIORITIES.map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </label>
                  <label style={{ flex: 1 }}>
                    Status
                    <select value={status} onChange={(e) => setStatus(e.target.value)}>
                      {REQ_STATUSES.map((s) => (
                        <option key={s} value={s}>{label({}, s)}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <button type="submit" className="story-submit">
                  <span>+</span> Add requirement
                </button>
              </form>
            ) : (
              <form className="story-form" onSubmit={onUpload}>
                <p className="muted">
                  Upload a requirement document. Text files (.txt/.md/.csv) are
                  extracted automatically; other formats are attached for you to
                  edit.
                </p>
                <label>
                  Title (optional)
                  <input
                    placeholder="Defaults to the file name"
                    value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                  />
                </label>
                <label>
                  Type
                  <select value={uploadType} onChange={(e) => setUploadType(e.target.value)}>
                    {REQ_TYPES.map((t) => (
                      <option key={t} value={t}>{REQ_TYPE_LABEL[t]}</option>
                    ))}
                  </select>
                </label>
                <label>
                  File
                  <input type="file" ref={fileRef} />
                </label>
                <button type="submit" className="story-submit" disabled={uploading}>
                  {uploading ? "Uploading…" : "Upload requirement"}
                </button>
              </form>
            )}
            {error && <p className="error">{error}</p>}
          </aside>

          <section className="stories-panel">
            <div className="stories-panel-head">
              <div>
                <div className="panel-kicker">Requirements</div>
                <h2>In this module</h2>
              </div>
              <span className="filter-chip on">All {requirements.length}</span>
            </div>
            {requirements.length === 0 ? (
              <div className="story-empty">
                <div className="story-empty-icon">+</div>
                <h3>No requirements yet</h3>
                <p>Add or upload your first requirement using the form on the left.</p>
              </div>
            ) : (
              <ul className="story-list">
                {requirements.map((r) => (
                  <li key={r.id} className="story-row">
                    <div className="story-row-index">R</div>
                    <div className="story-row-content">
                      <Link
                        to={`/projects/${projectId}/requirements/${r.id}`}
                        className="story-row-title"
                      >
                        {r.title}
                      </Link>
                      <p className="clamp">{r.raw_text}</p>
                      <div className="story-row-meta">
                        <span className="badge badge-blue">{REQ_TYPE_LABEL[r.req_type] || r.req_type}</span>
                        <span className="badge badge-grey">priority: {r.priority}</span>
                        <span className="badge badge-grey">{label({}, r.status)}</span>
                        {r.source_filename && (
                          <span className="badge badge-grey">📎 {r.source_filename}</span>
                        )}
                        <div className="story-row-actions">
                          <Link
                            to={`/projects/${projectId}/requirements/${r.id}`}
                            className="story-open"
                          >
                            Open <span>→</span>
                          </Link>
                          <button className="danger story-delete" onClick={() => onDelete(r.id)}>
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
