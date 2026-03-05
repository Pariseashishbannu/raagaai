import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth
export const register = (email, password) =>
  api.post('/auth/register', { email, password });

export const login = (email, password) =>
  api.post('/auth/login', { email, password });

export const getProfile = () => api.get('/auth/me');

// Ragas
export const listRagas = (melakartaOnly = false) =>
  api.get('/ragas', { params: { melakarta_only: melakartaOnly } });

export const getRaga = (ragaId) => api.get(`/ragas/${ragaId}`);

// Talas
export const listTalas = () => api.get('/talas');

// Generation
export const submitGeneration = (params) => api.post('/generate', params);

export const getJobStatus = (jobId) => api.get(`/generate/${jobId}`);

export const cancelJob = (jobId) => api.delete(`/generate/${jobId}`);

// Compositions
export const listCompositions = () => api.get('/compositions');

export const getComposition = (id) => api.get(`/compositions/${id}`);

// Health
export const healthCheck = () => api.get('/health');

export default api;
