import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  try {
    const stored = localStorage.getItem('auth_user');
    if (stored) {
      const { access_token } = JSON.parse(stored);
      if (access_token) {
        config.headers.Authorization = `Bearer ${access_token}`;
      }
    }
  } catch {}
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_user');
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

export const analyzeText = async (text) => {
  const response = await api.post('/api/ner/analyze-text', { text });
  return response.data;
};

export const analyzeUrl = async (url) => {
  const response = await api.post('/api/ner/analyze-url', { url });
  return response.data;
};

export const getStats = async () => {
  const response = await api.get('/api/admin/stats');
  return response.data;
};

export const startCrawl = async (url) => {
  const response = await api.post('/api/crawl/start', { url });
  return response.data;
};

export const getCrawlStatus = async (jobId) => {
  const response = await api.get(`/api/crawl/status/${jobId}`);
  return response.data;
};

export const startDiscovery = async (url) => {
  const response = await api.post('/api/crawl/discover', { url });
  return response.data;
};

export const getDiscoveryStatus = async (jobId) => {
  const response = await api.get(`/api/crawl/discover/${jobId}`);
  return response.data;
};

export const submitFeedback = async (data) => {
  const response = await api.post('/api/feedback/submit', data);
  return response.data;
};

export const exportFeedback = async () => {
  const response = await api.get('/api/feedback/export');
  return response.data;
};

export const loginUser = async (username, password) => {
  const response = await api.post('/api/auth/login', { username, password });
  return response.data;
};

export const getUsers = async () => {
  const response = await api.get('/api/users');
  return response.data;
};

export const createUser = async (data) => {
  const response = await api.post('/api/users', data);
  return response.data;
};

export const getReviewQueue = async () => {
  const response = await api.get('/api/feedback/queue');
  return response.data;
};

export const confirmCorrection = async (id) => {
  const response = await api.patch(`/api/feedback/${id}/confirm`);
  return response.data;
};

export const rejectCorrection = async (id) => {
  const response = await api.patch(`/api/feedback/${id}/reject`);
  return response.data;
};

export const startFilter = async () => {
  const response = await api.post('/api/pipeline/filter');
  return response.data;
};

export const getFilterStatus = async (jobId) => {
  const response = await api.get(`/api/pipeline/filter/${jobId}`);
  return response.data;
};

export const getPipelineStatus = async (jobId) => {
  const response = await api.get(`/api/pipeline/status/${jobId}`);
  return response.data;
};

export const startPipeline = async () => {
  const response = await api.post('/api/pipeline/process', {});
  return response.data;
};

export const getMe = async () => {
  const response = await api.get('/api/auth/me');
  return response.data;
};

// Labeling
export const getLabelingArticles = async () => {
  const response = await api.get('/api/labeling/articles');
  return response.data;
};

export const getLabelingArticle = async (articleId) => {
  const response = await api.get(`/api/labeling/articles/${articleId}`);
  return response.data;
};

export const getArticleSubmissions = async (articleId) => {
  const response = await api.get(`/api/labeling/articles/${articleId}/submissions`);
  return response.data;
};

export const saveSubmission = async (articleId, annotations, submit = false) => {
  const response = await api.post(`/api/labeling/articles/${articleId}/save`, {
    annotations,
    submit,
  });
  return response.data;
};

export const exportArticleAnnotations = async (articleId, format = 'json') => {
  const response = await api.get(`/api/labeling/articles/${articleId}/export`, {
    params: { format },
    responseType: 'blob',
  });
  return response;
};

export const assignArticle = async (articleId, labelerId, blindMode = false) => {
  const response = await api.post('/api/labeling/assign', {
    article_id: articleId,
    labeler_id: labelerId,
    blind_mode: blindMode,
  });
  return response.data;
};

// Role requests
export const requestRoleUpgrade = async () => {
  const response = await api.post('/api/role-requests/request');
  return response.data;
};

export const getRoleRequests = async () => {
  const response = await api.get('/api/role-requests');
  return response.data;
};

export const approveRoleRequest = async (requestId) => {
  const response = await api.patch(`/api/role-requests/${requestId}/approve`);
  return response.data;
};

export const rejectRoleRequest = async (requestId) => {
  const response = await api.patch(`/api/role-requests/${requestId}/reject`);
  return response.data;
};

export default api;
