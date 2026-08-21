const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TOKEN_KEY = "matf_token";
const MODEL_KEY = "matf_model";

// --- Per-run model selection (chosen in the UI dropdown) ------------------
// Stored in localStorage so every pipeline call picks it up automatically.
export function getModelSelection() {
  try {
    return JSON.parse(localStorage.getItem(MODEL_KEY)) || null;
  } catch {
    return null;
  }
}

export function setModelSelection(sel) {
  if (sel && sel.provider && sel.model) {
    localStorage.setItem(MODEL_KEY, JSON.stringify({ provider: sel.provider, model: sel.model }));
  } else {
    localStorage.removeItem(MODEL_KEY);
  }
}

// The request body attached to pipeline actions: the current model, or nothing
// (so the backend falls back to its configured default).
function modelBody() {
  const s = getModelSelection();
  return s && s.provider && s.model ? { provider: s.provider, model: s.model } : undefined;
}

// Wrap a pipeline call so the usage panel refreshes the moment it completes
// (each of these consumes provider quota). Fires only on success.
function pipe(promise) {
  return promise.then((r) => {
    try {
      window.dispatchEvent(new Event("matf:usage"));
    } catch {
      /* non-browser context */
    }
    return r;
  });
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { method = "GET", body, form, formData, auth = true } = {}) {
  const headers = {};
  const opts = { method, headers };

  if (formData) {
    opts.body = formData; // browser sets multipart Content-Type + boundary
  } else if (form) {
    opts.body = new URLSearchParams(form);
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (body !== undefined) {
    opts.body = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }

  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, opts);

  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail || `Request failed (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

const P = (projectId) => `/projects/${projectId}`;

export const api = {
  register: (email, password) =>
    request("/auth/register", { method: "POST", body: { email, password }, auth: false }),
  login: (email, password) =>
    request("/auth/login", { method: "POST", form: { username: email, password }, auth: false }),
  me: () => request("/auth/me"),

  llmMeta: () => request("/meta/llm", { auth: false }),
  listModels: () => request("/meta/models", { auth: false }),
  usage: (sessionSince) =>
    request(`/meta/usage${sessionSince ? `?session_since=${encodeURIComponent(sessionSince)}` : ""}`),

  listProjects: () => request("/projects"),
  createProject: (name, description) =>
    request("/projects", { method: "POST", body: { name, description } }),
  getProject: (id) => request(`/projects/${id}`),
  updateProject: (id, body) => request(`/projects/${id}`, { method: "PATCH", body }),
  deleteProject: (id) => request(`/projects/${id}`, { method: "DELETE" }),

  // --- Requirements (live directly under a project) ---
  listRequirements: (projectId) => request(`${P(projectId)}/requirements`),
  createRequirement: (projectId, body) =>
    request(`${P(projectId)}/requirements`, { method: "POST", body }),
  uploadRequirement: (projectId, formData) =>
    request(`${P(projectId)}/requirements/upload`, {
      method: "POST",
      formData,
    }),
  getRequirement: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}`),
  updateRequirement: (projectId, requirementId, body) =>
    request(`${P(projectId)}/requirements/${requirementId}`, { method: "PATCH", body }),
  deleteRequirement: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}`, { method: "DELETE" }),

  // --- Pipeline (operates on a requirement) ---
  // Each action attaches the current model selection (modelBody) so the chosen
  // provider+model drives that run; when none is set the backend uses its default.
  runRequirementAnalysis: (projectId, requirementId) =>
    pipe(
      request(`${P(projectId)}/requirements/${requirementId}/analyze`, {
        method: "POST",
        body: modelBody(),
      })
    ),
  getLatestAnalysis: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-analysis`),
  submitAcceptanceCriteria: (projectId, requirementId, criteria) =>
    request(`${P(projectId)}/requirements/${requirementId}/acceptance-criteria`, {
      method: "POST",
      body: { criteria },
    }),
  generateTestCases: (projectId, requirementId) =>
    pipe(
      request(`${P(projectId)}/requirements/${requirementId}/generate-test-cases`, {
        method: "POST",
        body: modelBody(),
      })
    ),
  getLatestTestCases: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-test-cases`),

  runReviewConsensus: (projectId, requirementId) =>
    pipe(
      request(`${P(projectId)}/requirements/${requirementId}/review-consensus`, {
        method: "POST",
        body: modelBody(),
      })
    ),
  getLatestReviewConsensus: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-review-consensus`),

  prioritize: (projectId, requirementId) =>
    pipe(
      request(`${P(projectId)}/requirements/${requirementId}/prioritize`, {
        method: "POST",
        body: modelBody(),
      })
    ),

  runCoverage: (projectId, requirementId) =>
    pipe(
      request(`${P(projectId)}/requirements/${requirementId}/coverage`, {
        method: "POST",
        body: modelBody(),
      })
    ),
  getLatestCoverage: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-coverage`),

  runQuality: (projectId, requirementId) =>
    pipe(
      request(`${P(projectId)}/requirements/${requirementId}/quality`, {
        method: "POST",
        body: modelBody(),
      })
    ),
  getLatestQuality: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-quality`),

  runBaseline: (projectId, requirementId) =>
    pipe(
      request(`${P(projectId)}/requirements/${requirementId}/baseline`, {
        method: "POST",
        body: modelBody(),
      })
    ),

  orchestrate: (projectId, requirementId) =>
    pipe(
      request(`${P(projectId)}/requirements/${requirementId}/orchestrate`, {
        method: "POST",
        body: modelBody(),
      })
    ),
  getLatestBaseline: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-baseline`),

  // --- Evaluation (fault-based experiments) ---
  // The experiment run attaches the current model selection (modelBody) so the
  // chosen provider+model drives the study; omitted -> backend default.
  listConditions: () => request("/evaluation/conditions"),
  seedBenchmark: () => pipe(request("/evaluation/benchmark/seed", { method: "POST" })),
  listBenchmarkItems: (datasetId) => request(`/evaluation/datasets/${datasetId}/items`),
  listExperiments: () => request("/evaluation/experiments"),
  createExperiment: (body) =>
    request("/evaluation/experiments", { method: "POST", body }),
  runExperiment: (experimentId) =>
    pipe(
      request(`/evaluation/experiments/${experimentId}/run`, {
        method: "POST",
        body: modelBody() ?? {},
      })
    ),
  getExperiment: (experimentId) => request(`/evaluation/experiments/${experimentId}`),
  getExperimentResults: (experimentId) =>
    request(`/evaluation/experiments/${experimentId}/results`),
  getExperimentItem: (experimentId, requirementId) =>
    request(`/evaluation/experiments/${experimentId}/items/${requirementId}`),

  // --- Export (§10): fetch the package as a blob and download it ---
  async exportPackage(projectId, requirementId, fmt) {
    const token = getToken();
    const res = await fetch(
      `${API_URL}${P(projectId)}/requirements/${requirementId}/export?fmt=${fmt}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} }
    );
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      const detail = data?.detail || `Export failed (${res.status})`;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const match = cd.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `test-design.${fmt}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
