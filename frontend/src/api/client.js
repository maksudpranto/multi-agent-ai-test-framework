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

async function request(path, { method = "GET", body, form, auth = true } = {}) {
  const headers = {};
  const opts = { method, headers };

  if (form) {
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

  listUserStories: (projectId) => request(`/projects/${projectId}/user-stories`),
  createUserStory: (projectId, title, raw_text) =>
    request(`/projects/${projectId}/user-stories`, {
      method: "POST",
      body: { title, raw_text },
    }),
  getUserStory: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}`),
  deleteUserStory: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}`, { method: "DELETE" }),

  runRequirementAnalysis: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/analyze`, {
      method: "POST",
    }),
  getLatestAnalysis: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/latest-analysis`),
  submitAcceptanceCriteria: (projectId, storyId, criteria) =>
    request(`/projects/${projectId}/user-stories/${storyId}/acceptance-criteria`, {
      method: "POST",
      body: { criteria },
    }),
  generateTestCases: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/generate-test-cases`, {
      method: "POST",
    }),
  getLatestTestCases: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/latest-test-cases`),

  runReviewConsensus: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/review-consensus`, {
      method: "POST",
    }),
  getLatestReviewConsensus: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/latest-review-consensus`),

  prioritize: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/prioritize`, {
      method: "POST",
    }),

  runCoverage: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/coverage`, {
      method: "POST",
    }),
  getLatestCoverage: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/latest-coverage`),

  runBaseline: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/baseline`, {
      method: "POST",
    }),
  getLatestBaseline: (projectId, storyId) =>
    request(`/projects/${projectId}/user-stories/${storyId}/latest-baseline`),
};
