import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

export const startCrawl = async (url, maxPages = 100) => {
  const response = await api.post('/api/crawl/start', { url, max_pages: maxPages });
  return response.data;
};

export const getCrawlStatus = async (jobId) => {
  const response = await api.get(`/api/crawl/status/${jobId}`);
  return response.data;
};

export default api;
