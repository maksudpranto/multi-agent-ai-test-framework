import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { REQ_TABS } from "../requirements/RequirementDetail";
import {
  PRIORITIES,
  REQ_STATUSES,
  REQ_TYPES,
  REQ_TYPE_LABEL,
  label,
} from "../requirements/constants";

const PRIORITY_CHIP = { high: "chip-red", medium: "chip-amber", low: "chip-grey" };

export default function ProjectDetail() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
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

  async function onCreate(e) {
    e.preventDefault();
    setError("");
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
      await api.uploadRequirement(projectId, fd);
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

  const highCount = requirements.filter((r) => r.priority === "high").length;

  return (
    <div className="content">
      <div>
        <p className="crumb">
          <Link to="/">Home</Link>
          <span className="sep">/</span>
          <span>{project?.name}</span>
        </p>
        <header className="page-head">
          <div>
            <h1>{project?.name}</h1>
            <p className="sub">
              {project?.description ||
                "Add requirements in any source form, then open one to run the AI test-design pipeline."}
            </p>
          </div>
        </header>
      </div>

      <section className="stats">
        <div className="stat">
          <div className="k">Requirements</div>
          <div className="v">{requirements.length}</div>
          <div className="h">In this project</div>
        </div>
        <div className="stat">
          <div className="k">High priority</div>
          <div className="v">{highCount}</div>
          <div className="h">Run these first</div>
        </div>
        <div className="stat">
          <div className="k">Ready / done</div>
          <div className="v">
            {requirements.filter((r) => r.status === "ready" || r.status === "done").length}
          </div>
          <div className="h">Past draft</div>
        </div>
      </section>

      <div className="workspace">
        {/* ---- Composer ---- */}
        <aside className="composer">
          <h3>New requirement</h3>
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
                  rows={7}
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
              <button type="submit">Add requirement</button>
            </form>
          ) : (
            <form className="form-v" onSubmit={onUpload}>
              <p className="form-hint">
                Upload a requirement document. Text files (.txt/.md/.csv) are
                extracted automatically; other formats are attached for you to
                edit.
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
              <button type="submit" disabled={uploading}>
                {uploading ? "Uploading…" : "Upload requirement"}
              </button>
            </form>
          )}
          {error && <p className="error" style={{ marginTop: 12 }}>{error}</p>}
        </aside>

        {/* ---- Requirements list ---- */}
        <section>
          <div className="projects-head">
            <h2>Requirements</h2>
            <span className="count">{requirements.length} total</span>
          </div>

          {requirements.length === 0 ? (
            <div className="empty">
              <h3>No requirements yet</h3>
              <p>Add or upload your first requirement using the panel on the left.</p>
            </div>
          ) : (
            <div className="rlist">
              {requirements.map((r) => (
                <div className="rcard" key={r.id}>
                  <div className="rcard-top">
                    <div className="ic">R</div>
                    <div style={{ minWidth: 0 }}>
                      <Link
                        to={`/projects/${projectId}/requirements/${r.id}`}
                        className="nm"
                      >
                        {r.title}
                      </Link>
                    </div>
                  </div>
                  {r.raw_text && <p className="ds">{r.raw_text}</p>}
                  <div className="rcard-foot">
                    <span className="chip chip-accent">
                      {REQ_TYPE_LABEL[r.req_type] || r.req_type}
                    </span>
                    <span className={`chip ${PRIORITY_CHIP[r.priority] || "chip-grey"}`}>
                      {r.priority}
                    </span>
                    <span className="chip chip-grey">{label({}, r.status)}</span>
                    {r.source_filename && (
                      <span className="chip chip-grey">📎 {r.source_filename}</span>
                    )}
                    <span className="spacer" />
                    <button className="danger btn-sm" onClick={() => onDelete(r.id)}>
                      Delete
                    </button>
                  </div>
                  <div className="rcard-links">
                    {REQ_TABS.map((t) => (
                      <Link
                        key={t.key}
                        to={`/projects/${projectId}/requirements/${r.id}${
                          t.key === "overview" ? "" : `?tab=${t.key}`
                        }`}
                      >
                        {t.label}
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
