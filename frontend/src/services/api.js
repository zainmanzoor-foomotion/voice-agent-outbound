import axios from "axios";

// All requests go through Vite's /api proxy -> FastAPI at :5000.
// In production, point this at your deployed backend URL.
const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

// --- Dashboard ---
export const fetchStats = () => api.get("/dashboard/stats").then((r) => r.data);

// --- Clients ---
export const fetchClients = (search = "") =>
  api
    .get("/clients", { params: search ? { search } : {} })
    .then((r) => r.data.clients);

export const fetchClient = (id) => api.get(`/clients/${id}`).then((r) => r.data);

export const deleteClient = (id) =>
  api.delete(`/clients/${id}`).then((r) => r.data);

// --- Calls ---
export const fetchCalls = (filters = {}) =>
  api.get("/calls", { params: filters }).then((r) => r.data.calls);

export const fetchCall = (id) => api.get(`/calls/${id}`).then((r) => r.data);

export const fetchTranscript = (callId) =>
  api.get(`/transcripts/${callId}`).then((r) => r.data);

// --- Actions ---
export const uploadClientsFile = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return api
    .post("/upload-clients", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};

export const startCalls = (limit = null) =>
  api.post("/start-calls", limit ? { limit } : {}).then((r) => r.data);

export const callClient = (clientId) =>
  api.post(`/call/${clientId}`).then((r) => r.data);

// --- Web Call (in-browser) ---
export const initWebCall = (clientId = null) =>
  api
    .post("/web-call/init", clientId ? { client_id: clientId } : {})
    .then((r) => r.data);

export const notifyWebCallStarted = (localCallId, vapiCallId) =>
  api
    .post(`/web-call/${localCallId}/started`, { vapi_call_id: vapiCallId })
    .then((r) => r.data);

// --- WhatsApp invitations ---
export const fetchInvitation = (clientId) =>
  api.get(`/invitations/${clientId}`).then((r) => r.data);

// --- Public "Click to talk" landing page ---
export const fetchInviteLanding = (token) =>
  api.get(`/invite/${token}`).then((r) => r.data);

export const startInviteCall = (token) =>
  api.post(`/invite/${token}/start`).then((r) => r.data);

export default api;
