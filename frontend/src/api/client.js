const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TOKEN_KEY = "matf_token";

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

  listProjects: () => request("/projects"),
  createProject: (name, description) =>
    request("/projects", { method: "POST", body: { name, description } }),
  getProject: (id) => request(`/projects/${id}`),
  deleteProject: (id) => request(`/projects/${id}`, { method: "DELETE" }),

  // --- Modules (§4) ---
  listModules: (projectId) => request(`${P(projectId)}/modules`),
  createModule: (projectId, body) =>
    request(`${P(projectId)}/modules`, { method: "POST", body }),
  getModule: (projectId, moduleId) => request(`${P(projectId)}/modules/${moduleId}`),
  updateModule: (projectId, moduleId, body) =>
    request(`${P(projectId)}/modules/${moduleId}`, { method: "PATCH", body }),
  deleteModule: (projectId, moduleId) =>
    request(`${P(projectId)}/modules/${moduleId}`, { method: "DELETE" }),

  // --- Requirements (§5) ---
  listRequirements: (projectId, moduleId) =>
    request(`${P(projectId)}/modules/${moduleId}/requirements`),
  createRequirement: (projectId, moduleId, body) =>
    request(`${P(projectId)}/modules/${moduleId}/requirements`, { method: "POST", body }),
  uploadRequirement: (projectId, moduleId, formData) =>
    request(`${P(projectId)}/modules/${moduleId}/requirements/upload`, {
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
  runRequirementAnalysis: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/analyze`, { method: "POST" }),
  getLatestAnalysis: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-analysis`),
  submitAcceptanceCriteria: (projectId, requirementId, criteria) =>
    request(`${P(projectId)}/requirements/${requirementId}/acceptance-criteria`, {
      method: "POST",
      body: { criteria },
    }),
  generateTestCases: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/generate-test-cases`, {
      method: "POST",
    }),
  getLatestTestCases: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-test-cases`),

  runReviewConsensus: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/review-consensus`, {
      method: "POST",
    }),
  getLatestReviewConsensus: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-review-consensus`),

  prioritize: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/prioritize`, { method: "POST" }),

  runCoverage: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/coverage`, { method: "POST" }),
  getLatestCoverage: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-coverage`),

  runBaseline: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/baseline`, { method: "POST" }),
  getLatestBaseline: (projectId, requirementId) =>
    request(`${P(projectId)}/requirements/${requirementId}/latest-baseline`),
};
